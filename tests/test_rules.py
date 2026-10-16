import copy
import json
import re
from pathlib import Path

import pytest

from engine import swiss
from engine.rules import STAGE_TYPES, EVENTS_DIR, RulesError, list_events, load_event_rules, stage_params, validate_rules
from pipeline import normalize
from pipeline.registry import STAGE_VIEWS
from pipeline.swiss_data import load_stage
from storage.db import connect
from tests.test_normalize import LEAGUE_ID, put
from tests.test_swiss import T2025

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def good():
    return json.loads((EVENTS_DIR / "worlds_2026.json").read_text(encoding="utf-8"))


def stage(data, slug):
    return next(s for s in data["stages"] if s["slug"] == slug)


def test_all_event_files_validate():
    events = list_events()
    assert {"worlds_2025", "worlds_2026"} <= set(events)
    for event in events:
        assert load_event_rules(event)["event"] == event


def test_every_stage_type_has_a_view():
    assert set(STAGE_TYPES) == set(STAGE_VIEWS)


def test_missing_rules_file_is_clear_error():
    with pytest.raises(RulesError, match="규칙 파일 없음"):
        load_event_rules("worlds_2099")


@pytest.mark.parametrize("mutate,message", [
    (lambda d: d.update(rule="free text"), "허용되지 않은 최상위 키"),
    (lambda d: d.pop("sources"), "필수 키 없음"),
    (lambda d: d.update(sources=[]), "sources"),
    (lambda d: d.update(verified_at="올해"), "verified_at"),
    (lambda d: d.update(schema_version=2), "schema_version"),
    (lambda d: d.update(event="worlds_2027"), "파일 이름"),
    (lambda d: stage(d, "swiss").update(type="round_robin"), "알 수 없는 type"),
    (lambda d: stage(d, "swiss")["params"].update(tiebreaker="x"), "읽지 않는 params 키"),
    (lambda d: stage(d, "swiss")["params"].update(win_target="3"), "win_target"),
    (lambda d: stage(d, "swiss")["params"]["best_of"].update(extra=5), "best_of"),
    (lambda d: stage(d, "knockouts")["params"].update(wiring="free_form"), "지원하지 않음"),
    (lambda d: stage(d, "knockouts")["params"].update(draw="random"), "지원하지 않음"),
    (lambda d: stage(d, "knockouts")["params"].update(round_sizes=[3, 2, 1]), "절반"),
    (lambda d: stage(d, "knockouts")["params"].update(round_labels=["8강"]), "round_labels"),
    (lambda d: stage(d, "play_ins")["params"]["slots"].update(wb_final=["W:lb_final", "W:r1b"]), "앞선 역할"),
    (lambda d: stage(d, "play_ins")["params"].update(advance_from="nowhere"), "advance_from"),
    (lambda d: stage(d, "play_ins")["params"].update(order="by_id"), "지원하지 않음"),
    (lambda d: d["stages"].append(copy.deepcopy(stage(d, "swiss"))), "slug 중복"),
    (lambda d: stage(d, "swiss").update(rule="text"), "허용되지 않은 키"),
])
def test_invalid_rules_are_rejected(good, mutate, message):
    mutate(good)
    with pytest.raises(RulesError, match=message):
        validate_rules(good, expected_event="worlds_2026")


def test_notes_can_hold_free_text(good):
    good["notes"]["anything"] = "자유 서술"
    stage(good, "swiss")["notes"]["anything"] = "자유 서술"
    validate_rules(good, expected_event="worlds_2026")


def test_no_dead_param_keys():
    source = "\n".join(p.read_text(encoding="utf-8") for folder in ("engine", "pipeline") for p in (ROOT / folder).glob("*.py")
                       if p.name != "rules.py")
    for stype, spec in STAGE_TYPES.items():
        for key in list(spec["required"]) + list(spec["optional"]):
            assert re.search(rf'\[["\']{key}["\']\]|\.get\(["\']{key}["\']', source), f"{stype}.{key} 를 코드가 읽지 않음"


def test_2025_rules_reproduce_2025_swiss_data():
    c = connect(":memory:")
    put(c, "getLeagues", "getLeagues.json")
    put(c, "getTournamentsForLeague", "getTournamentsForLeague.json", leagueId=LEAGUE_ID)
    put(c, "getTeams", "getTeams.json")
    put(c, "getSchedule", "getSchedule.json", leagueId=LEAGUE_ID)
    put(c, "getStandings", f"getStandings_{T2025}.json", tournamentId=T2025)
    normalize.run(c)
    params = stage_params(load_event_rules("worlds_2025"), "swiss")
    matches, _ = load_stage(c, "worlds_2025", "swiss")
    rounds = swiss.assign_rounds(matches, params["round_sizes"])
    assert swiss.validate(matches, rounds, params) == []
