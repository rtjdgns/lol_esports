import json
import re
from pathlib import Path

EVENTS_DIR = Path(__file__).resolve().parent.parent / "rules" / "events"


class RulesError(ValueError):
    pass


TOP_REQUIRED = {"schema_version", "event", "league_slug", "verified_at", "sources", "stages"}
TOP_ALLOWED = TOP_REQUIRED | {"entrants", "notes"}
STAGE_ALLOWED = {"slug", "type", "label", "params", "notes"}

STAGE_TYPES = {
    "swiss": {
        "required": {"win_target": int, "loss_limit": int, "round_sizes": list, "best_of": dict},
        "optional": {},
    },
    "single_elim": {
        "required": {"round_sizes": list, "round_labels": list, "wiring": str},
        "optional": {"draw": str},
    },
    "bracket_graph": {
        "required": {"roles": list, "labels": dict, "slots": dict, "advance_from": str, "order": str},
        "optional": {},
    },
}

ALLOWED_VALUES = {
    ("single_elim", "wiring"): {"adjacent_pairs"},
    ("single_elim", "draw"): {"none", "worlds_swiss_records"},
    ("bracket_graph", "order"): {"start_time"},
}


def _check_swiss(p, where):
    for key in ("win_target", "loss_limit"):
        if p[key] < 1:
            raise RulesError(f"{where}: {key} 는 1 이상")
    if not p["round_sizes"] or not all(isinstance(x, int) and x > 0 for x in p["round_sizes"]):
        raise RulesError(f"{where}: round_sizes 는 양의 정수 목록")
    bo = p["best_of"]
    if set(bo) != {"normal", "decisive"} or not all(isinstance(v, int) and v > 0 for v in bo.values()):
        raise RulesError(f"{where}: best_of 는 normal, decisive 정수 두 개만")


def _check_single_elim(p, where):
    sizes = p["round_sizes"]
    if not sizes or not all(isinstance(x, int) and x > 0 for x in sizes):
        raise RulesError(f"{where}: round_sizes 는 양의 정수 목록")
    if len(p["round_labels"]) != len(sizes):
        raise RulesError(f"{where}: round_labels 개수가 round_sizes 와 다름")
    if p["wiring"] == "adjacent_pairs":
        for a, b in zip(sizes, sizes[1:]):
            if a != 2 * b:
                raise RulesError(f"{where}: adjacent_pairs 는 라운드마다 경기 수가 절반이어야 함 {sizes}")
        if sizes[-1] != 1:
            raise RulesError(f"{where}: 마지막 라운드는 1경기여야 함")


def _check_bracket_graph(p, where):
    roles, slots, labels = p["roles"], p["slots"], p["labels"]
    if len(set(roles)) != len(roles):
        raise RulesError(f"{where}: roles 중복")
    if set(slots) != set(roles) or set(labels) != set(roles):
        raise RulesError(f"{where}: slots, labels 의 키가 roles 와 같아야 함")
    if p["advance_from"] not in roles:
        raise RulesError(f"{where}: advance_from 이 roles 에 없음")
    seen = set()
    for role in roles:
        srcs = slots[role]
        if len(srcs) != 2:
            raise RulesError(f"{where}: {role} 슬롯은 2개여야 함")
        for s in srcs:
            if s == "seed":
                continue
            m = re.fullmatch(r"([WL]):(\w+)", s)
            if not m or m.group(2) not in seen:
                raise RulesError(f"{where}: {role} 슬롯 '{s}' 은 앞선 역할의 W:/L: 참조여야 함")
        if srcs.count("seed") not in (0, 2):
            raise RulesError(f"{where}: {role} 의 seed 는 둘 다이거나 없어야 함")
        seen.add(role)


STAGE_CHECKS = {"swiss": _check_swiss, "single_elim": _check_single_elim, "bracket_graph": _check_bracket_graph}


def validate_rules(data, expected_event=None):
    missing = TOP_REQUIRED - set(data)
    if missing:
        raise RulesError(f"필수 키 없음: {sorted(missing)}")
    extra = set(data) - TOP_ALLOWED
    if extra:
        raise RulesError(f"허용되지 않은 최상위 키(설명은 notes 아래로): {sorted(extra)}")
    if data["schema_version"] != 1:
        raise RulesError(f"지원하지 않는 schema_version: {data['schema_version']}")
    if expected_event and data["event"] != expected_event:
        raise RulesError(f"event '{data['event']}' 가 파일 이름 '{expected_event}' 와 다름")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data["verified_at"])):
        raise RulesError("verified_at 은 YYYY-MM-DD")
    if not data["sources"] or not all(isinstance(s, str) and s for s in data["sources"]):
        raise RulesError("sources 는 비어 있지 않은 문자열 목록")
    slugs = set()
    for i, stage in enumerate(data["stages"]):
        where = f"stages[{i}]"
        extra = set(stage) - STAGE_ALLOWED
        if extra:
            raise RulesError(f"{where}: 허용되지 않은 키 {sorted(extra)}")
        for key in ("slug", "type", "label", "params"):
            if key not in stage:
                raise RulesError(f"{where}: '{key}' 없음")
        if stage["slug"] in slugs:
            raise RulesError(f"{where}: slug 중복 {stage['slug']}")
        slugs.add(stage["slug"])
        spec = STAGE_TYPES.get(stage["type"])
        if spec is None:
            raise RulesError(f"{where}: 알 수 없는 type '{stage['type']}' (허용: {sorted(STAGE_TYPES)})")
        params = stage["params"]
        allowed = set(spec["required"]) | set(spec["optional"])
        if set(params) - allowed:
            raise RulesError(f"{where}: type {stage['type']} 이 읽지 않는 params 키 {sorted(set(params) - allowed)}")
        for key, typ in {**spec["required"], **spec["optional"]}.items():
            if key in params and not isinstance(params[key], typ):
                raise RulesError(f"{where}: params.{key} 는 {typ.__name__}")
        for key in spec["required"]:
            if key not in params:
                raise RulesError(f"{where}: params.{key} 없음")
        for (t, key), values in ALLOWED_VALUES.items():
            if t == stage["type"] and key in params and params[key] not in values:
                raise RulesError(f"{where}: params.{key}='{params[key]}' 는 코드가 지원하지 않음 (허용: {sorted(values)})")
        STAGE_CHECKS[stage["type"]](params, where)
    entrants = data.get("entrants")
    if entrants is not None:
        if set(entrants) - {"direct", "play_in", "notes"}:
            raise RulesError("entrants 허용 키: direct, play_in, notes")
        for key in ("direct", "play_in"):
            if key in entrants and not all(isinstance(x, str) for x in entrants[key]):
                raise RulesError(f"entrants.{key} 는 team_id 문자열 목록")
    return data


def load_event_rules(event, events_dir=None):
    path = Path(events_dir or EVENTS_DIR) / f"{event}.json"
    if not path.exists():
        raise RulesError(f"규칙 파일 없음: {path}")
    return validate_rules(json.loads(path.read_text(encoding="utf-8")), expected_event=event)


def list_events(events_dir=None):
    return sorted(p.stem for p in Path(events_dir or EVENTS_DIR).glob("*.json"))


def get_stage(rules, slug):
    for stage in rules["stages"]:
        if stage["slug"] == slug:
            return stage
    raise RulesError(f"{rules['event']} 에 '{slug}' 단계 없음 (있는 단계: {[s['slug'] for s in rules['stages']]})")


def stage_params(rules, slug):
    return get_stage(rules, slug)["params"]
