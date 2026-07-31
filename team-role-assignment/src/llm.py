"""OpenAI client wrapper: JSON-mode call validated against a Pydantic schema, one retry.

ỔN ĐỊNH GIỮA CÁC LƯỢT CHẠY
Cùng một repo + cùng nhóm mà mỗi lần bấm ra hồ sơ và Task Graph khác hẳn nhau thì
không ai tin được kết quả. Hai nút vặn ở đây:

  temperature — mặc định 0. Càng cao model càng chọn token "ít khả năng hơn",
                nên danh sách kỹ năng và số đầu việc lệch nhiều giữa các lượt.
  seed        — cùng input thì cùng seed, nên OpenAI lấy cùng nhánh lấy mẫu.
                Seed suy ra từ băm của chính prompt: input đổi thì seed đổi theo,
                không phải hằng số cứng khiến mọi prompt dùng chung một nhánh.

Vẫn còn dao động NHỎ vì OpenAI chỉ hứa "best effort" — hạ tầng của họ đổi
(system_fingerprint đổi) thì kết quả lệch chút. Đó là mức mong muốn: khác nhau
nhưng ít. Muốn đa dạng hơn thì đặt LLM_TEMPERATURE trong .env.
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")
MODEL_SMART = os.getenv("OPENAI_MODEL_SMART", "gpt-4o")


CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "llm_cache"
_cache_lock = threading.Lock()


def _default_temperature() -> float:
    try:
        return max(0.0, min(2.0, float(os.getenv("LLM_TEMPERATURE", "0"))))
    except ValueError:
        return 0.0


def _cache_ttl() -> int:
    """Giây. 0 = tắt cache (eval phải gọi thật để đo đúng)."""
    try:
        return max(0, int(os.getenv("LLM_CACHE_TTL", "3600")))
    except ValueError:
        return 3600


def prompt_seed(*parts: str) -> int:
    """Seed ổn định suy ra từ nội dung prompt. Cùng input -> cùng seed."""
    h = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16)          # vừa khít int32 dương mà API chấp nhận


def _cache_key(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()


def _cache_read(key: str, ttl: int) -> str | None:
    """Trả nội dung JSON thô đã lưu, hoặc None nếu chưa có / quá hạn."""
    if ttl <= 0:
        return None
    f = CACHE_DIR / f"{key}.json"
    if not f.exists():
        return None
    try:
        entry = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - entry.get("at", 0) > ttl:
        return None
    return entry.get("raw")


def _cache_write(key: str, raw: str, model: str):
    with _cache_lock:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            (CACHE_DIR / f"{key}.json").write_text(
                json.dumps({"at": time.time(), "model": model, "raw": raw},
                           ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

_client: OpenAI | None = None

T = TypeVar("T", bound=BaseModel)


def client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("OPENAI_API_KEY chưa được điền trong file .env")
        _client = OpenAI(api_key=key)
    return _client


def call_json(model: str, system: str, user: str, schema: Type[T],
              temperature: float | None = None, max_tokens: int | None = None) -> T:
    """Call the model in JSON mode and validate output against `schema`.

    Retries once with the validation error appended so the model can self-correct.
    Lượt retry tốn thêm nguyên một call — luôn log ra để không âm thầm gấp đôi thời gian.

    temperature=None -> lấy LLM_TEMPERATURE (mặc định 0) để mọi luồng ổn định như nhau.
    """
    if temperature is None:
        temperature = _default_temperature()
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    sys_prompt = (
        f"{system}\n\n"
        f"Trả về DUY NHẤT một JSON object hợp lệ theo đúng JSON Schema sau, không thêm chữ nào khác:\n"
        f"{schema_json}"
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user},
    ]
    name = schema.__name__
    seed = prompt_seed(model, sys_prompt, user)

    # Cùng input thì dùng lại kết quả cũ. seed của OpenAI chỉ "best effort" —
    # đo thật thấy cùng seed vẫn ra 7 task lượt này, 5 task lượt sau. Cache là
    # thứ duy nhất bảo đảm test lại cùng một repo cho ra đúng cùng một Task Graph.
    ttl = _cache_ttl()
    key = _cache_key(model, sys_prompt, user, str(temperature))
    hit = _cache_read(key, ttl)
    if hit is not None:
        try:
            parsed = schema.model_validate_json(hit)
            print(f"[llm] {name:<20} {model:<12}   cache  seed={seed}", flush=True)
            return parsed
        except ValidationError:
            pass          # cache hỏng (đổi schema) -> gọi lại như thường

    last_err: Exception | None = None
    for attempt in range(2):
        t0 = time.time()
        kwargs = {"model": model, "messages": messages, "temperature": temperature,
                  "seed": seed, "response_format": {"type": "json_object"}}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = client().chat.completions.create(**kwargs)
        dt = time.time() - t0
        usage = getattr(resp, "usage", None)
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        fp = getattr(resp, "system_fingerprint", "") or "-"
        raw = resp.choices[0].message.content or "{}"
        try:
            parsed = schema.model_validate_json(raw)
            tag = " (lần 2)" if attempt else ""
            _cache_write(key, raw, model)
            # fingerprint đổi = OpenAI đổi hạ tầng -> đó là lúc kết quả lệch dù cùng seed
            print(f"[llm] {name:<20} {model:<12} {dt:5.1f}s  {out_tok:>5} tok out  "
                  f"T={temperature} seed={seed} fp={fp}{tag}", flush=True)
            return parsed
        except ValidationError as e:
            last_err = e
            print(f"[llm] {name:<20} {model:<12} {dt:5.1f}s  SCHEMA FAIL -> gọi lại: "
                  f"{str(e).splitlines()[0][:120]}", flush=True)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"JSON trả về không hợp lệ theo schema. Lỗi:\n{e}\nTrả lại JSON đã sửa, đúng schema.",
            })
    raise RuntimeError(f"LLM không trả được JSON hợp lệ sau 2 lần: {last_err}")
