import copy
import json
from collections import Counter
from dataclasses import replace

import pytest

from engine import swiss, visibility
from engine.rules import EVENTS_DIR, STAGE_TYPES, RulesError, load_event_rules, stage_params, validate_rules
from engine.visibility import PolicyError, evaluate_stage, load_policy, validate_entry, validate_policy
from pipeline import aliases, follow, normalize, show, visibility_data
from pipeline.swiss_data import load_stage
from storage.db import connect
from tests.test_normalize import LEAGUE_ID, put
from tests.test_swiss import T2025, T2026


@pytest.fixture(scope="module")
def conn():
    c = connect(":memory:")
    put(c, "getLeagues", "getLeagues.json")
    put(c, "getTournamentsForLeague", "getTournamentsForLeague.json", leagueId=LEAGUE_ID)
    put(c, "getTeams", "getTeams.json")
    put(c, "getSchedule", "getSchedule.json", leagueId=LEAGUE_ID)
    put(c, "getStandings", f"getStandings_{T2026}.json", tournamentId=T2026)
    put(c, "getStandings", f"getStandings_{T2025}.json", tournamentId=T2025)
    normalize.run(c)
    aliases.load_aliases(c)
    return c


def ctx(**kw):
    base = {"followed": set(), "participants": set(), "match_info": {}, "draw_done": None, "pre_draw_ready": None}
    base.update(kw)
    return base


def test_policy_file_valid_and_types_in_sync():
    policy = load_policy()
    assert set(policy["defaults"]) == set(visibility.MAX_LEVEL) == set(STAGE_TYPES)


@pytest.mark.parametrize("entry,stage_type,message", [
    ({"base": 1, "promote": [{"when": "free_text", "to": 2}]}, "swiss", "알 수 없는 조건"),
    ({"base": 1, "promote": [{"when": "draw_done", "to": 2}]}, "swiss", "쓸 수 없음"),
    ({"base": 1, "promote": [{"when": "decisive_match", "to": 3}]}, "swiss", "초과"),
    ({"base": 2, "promote": [{"when": "decisive_match", "to": 2}]}, "swiss", "초과"),
    ({"base": 4, "promote": []}, "swiss", "base"),
    ({"base": 1, "promote": [], "extra": 1}, "swiss", "base, promote"),
    ({"base": 1, "promote": [{"when": "decisive_match"}]}, "swiss", "when, to"),
    ({"base": 1, "promote": []}, "round_robin", "알 수 없는 단계 형식"),
])
def test_invalid_policy_entries_rejected(entry, stage_type, message):
    with pytest.raises(PolicyError, match=message):
        validate_entry(entry, stage_type)


def test_policy_must_cover_all_stage_types():
    policy = copy.deepcopy(load_policy())
    del policy["defaults"]["swiss"]
    with pytest.raises(PolicyError, match="모든 단계 형식"):
        validate_policy(policy)


def test_event_override_validated_against_stage_type():
    data = json.loads((EVENTS_DIR / "worlds_2026.json").read_text(encoding="utf-8"))
    data["display_policy"] = {"stages": {"swiss": {"base": 2, "promote": []}}}
    validate_rules(data, "worlds_2026")
    data["display_policy"] = {"stages": {"nowhere": {"base": 1, "promote": []}}}
    with pytest.raises(RulesError, match="단계가 없음"):
        validate_rules(data, "worlds_2026")
    data["display_policy"] = {"stages": {"swiss": {"base": 1, "promote": [{"when": "draw_done", "to": 2}]}}}
    with pytest.raises(RulesError, match="쓸 수 없음"):
        validate_rules(data, "worlds_2026")


def test_match_conditions_each_alone():
    entry = {"base": 1, "promote": [{"when": "followed_team_in_match", "to": 2}, {"when": "decisive_match", "to": 2}, {"when": "last_round_match", "to": 2}]}
    info = {
        "a": {"teams": ("T1", "X"), "state": "unstarted", "decisive": False, "last_round": False},
        "b": {"teams": ("Y", "Z"), "state": "unstarted", "decisive": True, "last_round": False},
        "c": {"teams": ("Y", "Z"), "state": "unstarted", "decisive": False, "last_round": True},
        "d": {"teams": ("Y", "Z"), "state": "unstarted", "decisive": False, "last_round": False},
        "e": {"teams": ("T1", "Z"), "state": "completed", "decisive": True, "last_round": True},
        "f": {"teams": (None, None), "state": "unstarted", "decisive": None, "last_round": True},
    }
    ev = evaluate_stage(entry, ctx(followed={"T1"}, match_info=info))
    assert ev["level"] == 1
    assert {k: v["reasons"] for k, v in ev["matches"].items()} == {
        "a": ["followed_team_in_match"], "b": ["decisive_match"], "c": ["last_round_match"], "f": ["last_round_match"]}


def test_stage_conditions_raise_level():
    entry = {"base": 1, "promote": [{"when": "pre_draw_ready", "to": 2}, {"when": "draw_done", "to": 3}, {"when": "followed_team_in_stage", "to": 2}]}
    assert evaluate_stage(entry, ctx())["level"] == 1
    assert evaluate_stage(entry, ctx(pre_draw_ready=True))["level"] == 2
    assert evaluate_stage(entry, ctx(pre_draw_ready=False, draw_done=True))["level"] == 3
    ev = evaluate_stage(entry, ctx(participants={"A"}, followed={"A"}))
    assert ev["level"] == 2 and ev["stage_reasons"] == ["followed_team_in_stage"]


def test_swiss_match_contexts_decisive_equals_bo3_in_2025(conn):
    params = stage_params(load_event_rules("worlds_2025"), "swiss")
    matches, _ = load_stage(conn, "worlds_2025", "swiss")
    info = swiss.match_contexts(matches, params)
    with_bo = [m for m in matches if m.best_of]
    assert all(info[m.match_id]["decisive"] == (m.best_of == 3) for m in with_bo)
    assert sum(1 for i in info.values() if i["decisive"]) == 13
    assert sum(1 for i in info.values() if i["last_round"]) == 3


def test_2026_schedule_bo_distribution_matches_rule(conn):
    params = stage_params(load_event_rules("worlds_2026"), "swiss")
    matches, _ = load_stage(conn, "worlds_2026", "swiss")
    rounds = swiss.assign_rounds(matches, params["round_sizes"])
    got = Counter((rounds[m.match_id], m.best_of) for m in matches)
    assert got == {(1, 1): 8, (2, 1): 8, (3, 1): 4, (3, 3): 4, (4, 3): 6, (5, 3): 3}


def test_contexts_for_2026(conn):
    rules = load_event_rules("worlds_2026")
    ctxs = visibility_data.build_contexts(conn, "worlds_2026", rules, set())
    assert ctxs["knockouts"]["draw_done"] is False and ctxs["knockouts"]["pre_draw_ready"] is False
    assert sum(1 for i in ctxs["play_ins"]["match_info"].values() if i["decisive"]) == 3
    assert sum(1 for i in ctxs["play_ins"]["match_info"].values() if i["last_round"]) == 1
    swiss_info = ctxs["swiss"]["match_info"]
    assert all(i["decisive"] is None for i in swiss_info.values())
    assert sum(1 for i in swiss_info.values() if i["last_round"]) == 3


def test_policy_levels_for_2026_and_follow_changes_nothing_without_known_teams(conn):
    rules, policy = load_event_rules("worlds_2026"), load_policy()
    levels = {}
    for stage in rules["stages"]:
        c = visibility_data.build_contexts(conn, "worlds_2026", rules, {"nobody"})[stage["slug"]]
        levels[stage["slug"]] = evaluate_stage(visibility.resolve_entry(policy, rules, stage), c)["level"]
    assert levels == {"play_ins": 2, "swiss": 1, "knockouts": 1}


def test_knockout_level_goes_to_3_after_draw(conn):
    rules, policy = load_event_rules("worlds_2025"), load_policy()
    stage = next(s for s in rules["stages"] if s["slug"] == "knockouts")
    c = visibility_data.build_contexts(conn, "worlds_2025", rules, set())["knockouts"]
    assert c["draw_done"] is True
    assert evaluate_stage(visibility.resolve_entry(policy, rules, stage), c)["level"] == 3


def test_event_override_beats_default(conn):
    rules, policy = copy.deepcopy(load_event_rules("worlds_2026")), load_policy()
    rules["display_policy"] = {"stages": {"swiss": {"base": 2, "promote": []}}}
    stage = next(s for s in rules["stages"] if s["slug"] == "swiss")
    assert visibility.resolve_entry(policy, rules, stage)["base"] == 2


def test_show_end_to_end_2026(conn):
    text = "\n".join(show.render_show(conn, "worlds_2026", followed=set()))
    assert "■ 플레이-인 · 수준 2" in text and "■ 스위스 · 수준 1" in text and "■ 토너먼트 · 수준 1" in text
    assert "경우의 수가 걸린 경기" in text and "마지막 라운드" in text
    assert "스위스 경우의 수" not in text


def test_round3_promotions_for_followed_and_decisive_matches(conn):
    gen = "100205573495116443"
    rules = load_event_rules("worlds_2025")
    stage = next(s for s in rules["stages"] if s["slug"] == "swiss")
    params = stage["params"]
    matches, _ = load_stage(conn, "worlds_2025", "swiss")
    rounds = swiss.assign_rounds(matches, params["round_sizes"])
    hypothetical = [replace(m, state="unstarted", wins=(0, 0)) if rounds[m.match_id] == 3 else m
                    for m in matches if rounds[m.match_id] <= 3]
    info = swiss.match_contexts(hypothetical, params)
    c = ctx(followed={gen}, participants={t for m in hypothetical for t in m.team_ids},
            match_info={m.match_id: {"teams": m.team_ids, "state": m.state, "decisive": info[m.match_id]["decisive"],
                                     "last_round": info[m.match_id]["last_round"]} for m in hypothetical})
    ev = evaluate_stage(visibility.resolve_entry(load_policy(), rules, stage), c)
    round3 = [m for m in hypothetical if rounds[m.match_id] == 3]
    by_reason = {r: {mid for mid, h in ev["matches"].items() if r in h["reasons"]}
                 for r in ("decisive_match", "followed_team_in_match", "last_round_match")}
    assert by_reason["decisive_match"] == {m.match_id for m in round3 if m.best_of == 3}
    assert len(by_reason["decisive_match"]) == 4
    assert by_reason["followed_team_in_match"] == {m.match_id for m in round3 if gen in m.team_ids}
    assert len(by_reason["followed_team_in_match"]) == 1
    assert by_reason["last_round_match"] == set()
    assert ev["level"] == 1
