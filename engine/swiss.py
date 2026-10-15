import json
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "worlds_2026.json"


def load_rules(path=RULES_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def team_status(wins, losses, win_target=3, loss_limit=3):
    if wins >= win_target:
        return "진출 확정"
    if losses >= loss_limit:
        return "탈락 확정"
    parts = [f"{win_target - wins}승 시 진출", f"{loss_limit - losses}패 시 탈락"]
    if wins == win_target - 1:
        parts.append("진출 결정전")
    if losses == loss_limit - 1:
        parts.append("탈락 결정전")
    return " / ".join(parts)
