import json
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parent.parent / "rules" / "display_policy.json"

MAX_LEVEL = {"swiss": 2, "bracket_graph": 2, "single_elim": 3}
ALL_TYPES = set(MAX_LEVEL)


class PolicyError(ValueError):
    pass


def _followed_team_in_match(ctx, mid):
    return bool({t for t in ctx["match_info"][mid]["teams"] if t} & ctx["followed"])


def _decisive_match(ctx, mid):
    return ctx["match_info"][mid]["decisive"] is True


def _last_round_match(ctx, mid):
    return ctx["match_info"][mid]["last_round"] is True


def _followed_team_in_stage(ctx):
    return bool(ctx["participants"] & ctx["followed"])


def _draw_done(ctx):
    return ctx["draw_done"] is True


def _pre_draw_ready(ctx):
    return ctx["pre_draw_ready"] is True


CONDITIONS = {
    "followed_team_in_match": ("match", ALL_TYPES, _followed_team_in_match),
    "decisive_match": ("match", ALL_TYPES, _decisive_match),
    "last_round_match": ("match", ALL_TYPES, _last_round_match),
    "followed_team_in_stage": ("stage", ALL_TYPES, _followed_team_in_stage),
    "draw_done": ("stage", {"single_elim"}, _draw_done),
    "pre_draw_ready": ("stage", {"single_elim"}, _pre_draw_ready),
}

REASON_KO = {
    "followed_team_in_match": "팔로우한 팀 경기",
    "decisive_match": "진출·탈락이 걸린 경기",
    "last_round_match": "마지막 라운드",
    "followed_team_in_stage": "팔로우한 팀이 있는 단계",
    "draw_done": "대진 추첨 완료",
    "pre_draw_ready": "추첨 대기(앞 단계 종료)",
}


def validate_entry(entry, stage_type, where="display_policy"):
    if stage_type not in MAX_LEVEL:
        raise PolicyError(f"{where}: 알 수 없는 단계 형식 {stage_type}")
    if not isinstance(entry, dict) or set(entry) - {"base", "promote"} or set(entry) != {"base", "promote"}:
        raise PolicyError(f"{where}: base, promote 만 허용")
    top = MAX_LEVEL[stage_type]
    if not isinstance(entry["base"], int) or not 1 <= entry["base"] <= top:
        raise PolicyError(f"{where}: base 는 1~{top} ({stage_type} 의 최대 수준)")
    if not isinstance(entry["promote"], list):
        raise PolicyError(f"{where}: promote 는 목록")
    for i, rule in enumerate(entry["promote"]):
        if not isinstance(rule, dict) or set(rule) != {"when", "to"}:
            raise PolicyError(f"{where}.promote[{i}]: when, to 만 허용")
        cond = CONDITIONS.get(rule["when"])
        if cond is None:
            raise PolicyError(f"{where}.promote[{i}]: 알 수 없는 조건 '{rule['when']}' (허용: {sorted(CONDITIONS)})")
        if stage_type not in cond[1]:
            raise PolicyError(f"{where}.promote[{i}]: 조건 '{rule['when']}' 은 {stage_type} 에 쓸 수 없음")
        if not isinstance(rule["to"], int) or not entry["base"] < rule["to"] <= top:
            raise PolicyError(f"{where}.promote[{i}]: to 는 base({entry['base']}) 초과 {top} 이하")
    return entry


def validate_policy(policy):
    if set(policy) - {"schema_version", "defaults", "notes"} or not {"schema_version", "defaults"} <= set(policy):
        raise PolicyError("display_policy.json 은 schema_version, defaults, notes 만 허용")
    if policy["schema_version"] != 1:
        raise PolicyError("지원하지 않는 schema_version")
    if set(policy["defaults"]) != set(MAX_LEVEL):
        raise PolicyError(f"defaults 는 모든 단계 형식을 정의해야 함: {sorted(MAX_LEVEL)}")
    for stage_type, entry in policy["defaults"].items():
        validate_entry(entry, stage_type, f"defaults.{stage_type}")
    return policy


def validate_event_override(section, stages):
    if not isinstance(section, dict) or set(section) - {"stages", "notes"}:
        raise PolicyError("display_policy 는 stages, notes 만 허용")
    by_slug = {s["slug"]: s["type"] for s in stages}
    for slug, entry in section.get("stages", {}).items():
        if slug not in by_slug:
            raise PolicyError(f"display_policy.stages: '{slug}' 단계가 없음")
        validate_entry(entry, by_slug[slug], f"display_policy.stages.{slug}")


def load_policy(path=None):
    return validate_policy(json.loads(Path(path or POLICY_PATH).read_text(encoding="utf-8")))


def resolve_entry(policy, rules, stage):
    override = rules.get("display_policy", {}).get("stages", {}).get(stage["slug"])
    return override if override is not None else policy["defaults"][stage["type"]]


def evaluate_stage(entry, ctx):
    level, stage_reasons, matches = entry["base"], [], {}
    for rule in entry["promote"]:
        scope, _, fn = CONDITIONS[rule["when"]]
        if scope == "stage":
            if fn(ctx):
                level = max(level, rule["to"])
                stage_reasons.append(rule["when"])
        else:
            for mid, info in ctx["match_info"].items():
                if info["state"] == "completed" or not fn(ctx, mid):
                    continue
                m = matches.setdefault(mid, {"level": entry["base"], "reasons": []})
                m["level"] = max(m["level"], rule["to"])
                m["reasons"].append(rule["when"])
    return {"base": entry["base"], "level": level, "stage_reasons": stage_reasons, "matches": matches}
