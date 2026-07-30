"""Dựng toàn bộ vector từ seed/ -> seed/.cache/.

Chạy:
    python scripts/build_graphs.py                # crawl + LLM, dùng cache có sẵn
    python scripts/build_graphs.py --crawl-only   # chỉ crawl GitHub, không gọi LLM
    python scripts/build_graphs.py --force        # bỏ qua cache, làm lại từ đầu
    python scripts/build_graphs.py --lab lab2     # chỉ dựng 1 lab

Thứ tự bắt buộc: crawl -> gain học viên -> observed của lab -> required của lab
(vì required lấy cả phần quan sát từ hành vi cohort).
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.crawl import (cache_path, crawl_lab, crawl_student_lab,      # noqa: E402
                       read_cache, write_cache)
from src.extract import lab_declared, student_lab_gain                 # noqa: E402
from src.seed_loader import lab_order, load_all                        # noqa: E402
from src.vectors import (accumulate_student, lab_observed,             # noqa: E402
                         lab_required)

OUT = ROOT / "seed" / ".cache"


def step(msg: str):
    print(f"\n=== {msg} ===")


def cached(path, force: bool, build):
    """Đọc cache nếu có, không thì build rồi ghi."""
    if not force:
        hit = read_cache(path)
        if hit is not None:
            return hit, True
    data = build()
    write_cache(path, data)
    return data, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="bỏ qua cache")
    ap.add_argument("--crawl-only", action="store_true", help="không gọi LLM")
    ap.add_argument("--lab", default="", help="chỉ dựng 1 lab")
    args = ap.parse_args()

    seed = load_all()
    skills, labs, students = seed["skills"], seed["labs"], seed["students"]
    order = lab_order(labs)
    targets = [args.lab] if args.lab else order
    for t in targets:
        if t not in labs:
            print(f"Lab '{t}' không có trong labs.json. Có: {', '.join(order)}")
            return 1

    print(f"Trục: {len(skills)} | Lab: {', '.join(order)} | Học viên: {len(students)}")

    # ---- 1. Crawl bằng chứng thô ----
    step("1. Crawl GitHub")
    raw_student: dict[tuple[str, str], dict] = {}
    for s in students:
        for e in s["labs"]:
            if e["lab"] not in targets:
                continue
            p = cache_path("raw", s["mssv"], e["lab"])
            data, hit = cached(p, args.force, lambda s=s, e=e: crawl_student_lab(s, e))
            raw_student[(s["mssv"], e["lab"])] = data
            c = data.get("commits", {})
            flag = "cache" if hit else "fetch"
            note = data.get("repo_error") or f"{c.get('count',0)} commit ({c.get('attribution')})"
            print(f"  [{flag}] {s['name']:<22} {e['lab']:<6} {note}"
                  f" | report={'Y' if data.get('has_report') else 'n'}"
                  f" group={'Y' if data.get('has_group_report') else 'n'}")

    raw_lab: dict[str, dict] = {}
    for name in targets:
        p = cache_path("rawlab", name)
        data, hit = cached(p, args.force, lambda n=name: crawl_lab(labs[n]))
        raw_lab[name] = data
        ok_docs = sum(1 for d in data["docs"] if d["ok"])
        print(f"  [{'cache' if hit else 'fetch'}] LAB {name:<6} {ok_docs}/{len(data['docs'])} tài liệu đọc được")

    if args.crawl_only:
        print("\n--crawl-only: dừng trước bước LLM. Xem seed/.cache/raw__*.json")
        return 0

    # ---- 2. Gain từng học viên từng lab ----
    step("2. Vector năng lực từng lab (LLM)")
    gains: dict[str, list[dict]] = {s["mssv"]: [] for s in students}
    gains_by_lab: dict[str, list[dict]] = {n: [] for n in targets}
    for s in students:
        for e in s["labs"]:
            if e["lab"] not in targets:
                continue
            p = cache_path("gain", s["mssv"], e["lab"])
            raw = raw_student[(s["mssv"], e["lab"])]
            data, hit = cached(p, args.force,
                               lambda r=raw: student_lab_gain(r, skills))
            gains[s["mssv"]].append(data)
            gains_by_lab[e["lab"]].append(data)
            top = sorted(data["gains"].items(), key=lambda x: -x[1])[:4]
            shown = ", ".join(f"{k} {v:.2f}" for k, v in top) or "(không có bằng chứng)"
            print(f"  [{'cache' if hit else 'LLM  '}] {s['name']:<22} {e['lab']:<6} {shown}")
            if data["dropped_skills"]:
                print(f"          ! bỏ skill ngoài registry: {data['dropped_skills']}")

    # ---- 3. Vector tích luỹ của học viên ----
    step("3. Vector tích luỹ qua các lab")
    profiles = []
    for s in students:
        acc = accumulate_student(gains[s["mssv"]], order)
        prof = {"mssv": s["mssv"], "name": s["name"], "github": s["github_login"], **acc}
        profiles.append(prof)
        write_cache(cache_path("profile", s["mssv"]), prof)
        top = sorted(prof["vector"].items(), key=lambda x: -x[1])[:5]
        print(f"  {s['name']:<22} {len(prof['vector'])} trục | "
              + ", ".join(f"{k} {v:.2f}" for k, v in top))
        for skill, hist in prof["history"].items():
            if len(hist) > 1:
                path = " -> ".join(f"{h['lab']}:{h['after']:.2f}" for h in hist)
                print(f"          ↑ {skill}: {path}")

    # ---- 4. Vector yêu cầu của lab (declared + observed + kế thừa) ----
    step("4. Vector yêu cầu của lab (LLM + quan sát cohort)")
    declared, observed = {}, {}
    for name in targets:
        p = cache_path("declared", name)
        data, hit = cached(p, args.force, lambda n=name: lab_declared(raw_lab[n], skills))
        declared[name] = data
        observed[name] = lab_observed(gains_by_lab[name], skills)
        write_cache(cache_path("observed", name), observed[name])
        print(f"  [{'cache' if hit else 'LLM  '}] {name}: khai báo {len(data['weights'])} trục "
              f"(confidence={data['confidence']}) | quan sát {len(observed[name])} trục")
        if data["dropped_skills"]:
            print(f"          ! bỏ skill ngoài registry: {data['dropped_skills']}")

    # Lab cha phải có vector đầy đủ, nếu không phần kế thừa của lab con bị hụt.
    for name in order:
        if name in declared:
            continue
        d = read_cache(cache_path("declared", name))
        o = read_cache(cache_path("observed", name))
        if d is None:
            print(f"  ! lab '{name}' chưa dựng — lab phụ thuộc nó sẽ kế thừa thiếu. "
                  f"Chạy không kèm --lab để dựng đủ.")
        declared[name] = d or {"weights": {}, "summary": "", "confidence": "low",
                               "reasons": {}, "dropped_skills": []}
        observed[name] = o or {}

    for name in targets:
        req = lab_required(name, labs, declared, observed)
        write_cache(cache_path("lab", name), req)
        src = req["source"]
        print(f"\n  LAB {name}: {len(req['vector'])} trục")
        for skill, w in list(req["vector"].items())[:10]:
            tag = ("đề bài" if skill in src["declared"]
                   else "quan sát" if skill in src["observed_only"] else "kế thừa")
            print(f"      {skill:<22} {w:.2f}  [{tag}]")
        if src["observed_only"]:
            print(f"      * cohort dùng mà đề bài không nói: {src['observed_only']}")
        if src["inherited_only"]:
            print(f"      * kế thừa từ lab trước: {src['inherited_only']}")

    print(f"\nXong. Cache: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
