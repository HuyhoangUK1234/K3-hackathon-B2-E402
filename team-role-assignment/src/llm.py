"""OpenAI client wrapper: JSON-mode call validated against a Pydantic schema, one retry."""
import json
import os
import time
from typing import Type, TypeVar

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()

MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")
MODEL_SMART = os.getenv("OPENAI_MODEL_SMART", "gpt-4o")

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
              temperature: float = 0.2, max_tokens: int | None = None) -> T:
    """Call the model in JSON mode and validate output against `schema`.

    Retries once with the validation error appended so the model can self-correct.
    Lượt retry tốn thêm nguyên một call — luôn log ra để không âm thầm gấp đôi thời gian.
    """
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
    last_err: Exception | None = None
    for attempt in range(2):
        t0 = time.time()
        kwargs = {"model": model, "messages": messages, "temperature": temperature,
                  "response_format": {"type": "json_object"}}
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        resp = client().chat.completions.create(**kwargs)
        dt = time.time() - t0
        usage = getattr(resp, "usage", None)
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        raw = resp.choices[0].message.content or "{}"
        try:
            parsed = schema.model_validate_json(raw)
            tag = " (lần 2)" if attempt else ""
            print(f"[llm] {name:<20} {model:<12} {dt:5.1f}s  {out_tok:>5} tok out{tag}",
                  flush=True)
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
