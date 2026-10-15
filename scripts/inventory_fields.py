import json
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw_samples"
OUT = Path(__file__).resolve().parent.parent / "docs" / "data_inventory.md"


def walk(obj, prefix, acc):
    if isinstance(obj, dict):
        for k, v in obj.items():
            walk(v, f"{prefix}.{k}" if prefix else k, acc)
    elif isinstance(obj, list):
        acc.setdefault(prefix + "[]", {"types": set(), "examples": [], "nonnull": 0, "total": 0})
        for item in obj:
            if isinstance(item, (dict, list)):
                walk(item, prefix + "[]", acc)
            else:
                record(acc, prefix + "[]", item)
    else:
        record(acc, prefix, obj)


def record(acc, path, value):
    e = acc.setdefault(path, {"types": set(), "examples": [], "nonnull": 0, "total": 0})
    e["types"].add(type(value).__name__)
    e["total"] += 1
    if value not in (None, "", [], {}):
        e["nonnull"] += 1
        if len(e["examples"]) < 2 and str(value) not in e["examples"]:
            e["examples"].append(str(value)[:40])


def main():
    lines = ["# 수집 필드 목록", "", "`scripts/inventory_fields.py`가 `data/raw_samples/` 원본에서 생성. 채움률 = null/빈 값이 아닌 비율.", ""]
    for f in sorted(RAW.glob("*.json")):
        acc = {}
        walk(json.loads(f.read_text(encoding="utf-8")), "", acc)
        lines += [f"## {f.stem}", "", "| 경로 | 타입 | 채움률 | 예시 |", "|---|---|---|---|"]
        for path, e in sorted(acc.items()):
            if e["total"] == 0:
                continue
            rate = f"{e['nonnull']}/{e['total']}"
            lines.append(f"| `{path}` | {','.join(sorted(e['types']))} | {rate} | {' ; '.join(e['examples'])} |")
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")


main()
