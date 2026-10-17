import json
from collections import Counter
from pathlib import Path

import pytest

from engine.standings import derive_rounds, head_to_head, rank, split_deciders, tally
from engine.types import StageMatch

FIX = Path(__file__).resolve().parent / "fixtures"


def sections():
    data = json.loads((FIX / "lck_ranked_sections.json").read_text(encoding="utf-8"))["sections"]
    return {(s["tournament"], s["stage"], s["section"]): s for s in data}


def api_matches(s):
    return [StageMatch(m[0], "%08d" % i, 3, "completed", (m[1], m[2]), (m[3], m[4])) for i, m in enumerate(s["matches"])]


def season_matches(stage):
    rows = json.loads((FIX / "lck_2026_matches.json").read_text(encoding="utf-8"))["stages"][stage]
    return [StageMatch(r[0], r[1], r[2], "completed", (r[3], r[5]), (r[4], r[6])) for r in rows]


def regular_rounds(key):
    return 1 if key[0] in ("lck_split_1_2026", "lck_cup_2025") else 2


VALIDATED = [k for k in sections() if k[0] != "lck_split_3_2026" and k[0] != "lck_split_3_2025"]


@pytest.mark.parametrize("key", VALIDATED)
def test_rank_matches_api_order(key):
    s = sections()[key]
    teams = [t[0] for t in s["api_order"]]
    regular, deciders = split_deciders(api_matches(s), regular_rounds(key))
    table, unresolved = rank(regular, teams, deciders=deciders)
    assert [r.team_id for r in table] == teams
    assert unresolved == []


@pytest.mark.parametrize("group", ["레전드 그룹", "라이즈 그룹"])
def test_2026_groups_use_cumulative_record_from_regular_season(group):
    secs = sections()
    s = secs[("lck_split_3_2026", "groups", group)]
    teams = [t[0] for t in s["api_order"]]
    reg_r, reg_d = split_deciders(api_matches(secs[("lck_split_2_2026", "regular_season", "정규 리그")]), 2)
    grp_r, grp_d = split_deciders(api_matches(s), 2)
    table, unresolved = rank(reg_r + grp_r, teams, deciders=reg_d + grp_d)
    assert [r.team_id for r in table] == teams and unresolved == []
    group_only, _ = rank(grp_r, teams, deciders=grp_d)
    assert [r.team_id for r in group_only] != teams


def test_2026_group_assignment_is_regular_season_top5_and_bottom5():
    secs = sections()
    regular = [t[0] for t in secs[("lck_split_2_2026", "regular_season", "정규 리그")]["api_order"]]
    legend = {t[0] for t in secs[("lck_split_3_2026", "groups", "레전드 그룹")]["api_order"]}
    rise = {t[0] for t in secs[("lck_split_3_2026", "groups", "라이즈 그룹")]["api_order"]}
    assert legend == set(regular[:5]) and rise == set(regular[5:])


def test_2025_legend_group_is_a_known_deviation():
    secs = sections()
    s = secs[("lck_split_3_2025", "groups", "레전드 그룹")]
    teams = [t[0] for t in s["api_order"]]
    code = {t[0]: t[1] for t in s["api_order"]}
    reg_r, reg_d = split_deciders(api_matches(secs[("lck_split_2_2025", "regular_season", "정규 리그")]), 2)
    grp_r, grp_d = split_deciders(api_matches(s), 3)
    table, _ = rank(reg_r + grp_r, teams, deciders=reg_d + grp_d)
    mine = [code[r.team_id] for r in table]
    api = [code[t] for t in teams]
    assert api == ["GEN", "T1", "HLE", "KT", "NS"] and mine == ["GEN", "HLE", "T1", "KT", "NS"]


def test_2025_rise_group_matches_with_three_round_groups():
    secs = sections()
    s = secs[("lck_split_3_2025", "groups", "라이즈 그룹")]
    teams = [t[0] for t in s["api_order"]]
    reg_r, reg_d = split_deciders(api_matches(secs[("lck_split_2_2025", "regular_season", "정규 리그")]), 2)
    grp_r, grp_d = split_deciders(api_matches(s), 3)
    table, unresolved = rank(reg_r + grp_r, teams, deciders=reg_d + grp_d)
    assert [r.team_id for r in table] == teams and unresolved == []


def test_rounds_for_regular_season_derived_from_meetings():
    ms = season_matches("regular_season")
    rounds = derive_rounds(ms)
    assert Counter(rounds.values()) == {1: 45, 2: 45}
    first = max(m.start_time for m in ms if rounds[m.match_id] == 1)
    second = min(m.start_time for m in ms if rounds[m.match_id] == 2)
    assert first < second
    assert len({frozenset(m.team_ids) for m in ms}) == 45


def test_rounds_for_groups_use_offset():
    ms = season_matches("groups")
    rounds = derive_rounds(ms, offset=2)
    assert Counter(rounds.values()) == {3: 20, 4: 20}
    assert max(m.start_time for m in ms if rounds[m.match_id] == 3) < min(m.start_time for m in ms if rounds[m.match_id] == 4)


def test_decider_match_is_separated_and_breaks_final_tie():
    s = sections()[("lck_split_2_2025", "regular_season", "정규 리그")]
    regular, deciders = split_deciders(api_matches(s), 2)
    assert len(regular) == 90 and len(deciders) == 1
    rows = tally(regular)
    assert Counter((r.wins, r.losses) for r in rows.values())[(10, 8)] == 3


def test_unresolved_tie_is_reported_not_guessed():
    ms = [StageMatch("1", "1", 3, "completed", ("A", "B"), (2, 0)), StageMatch("2", "2", 3, "completed", ("B", "A"), (2, 0))]
    table, unresolved = rank(ms)
    assert unresolved == [["A", "B"]]


def test_unknown_tiebreaker_rejected():
    with pytest.raises(ValueError, match="지원하지 않는 동률 기준"):
        rank([], tiebreakers=("coin_flip",))


def test_head_to_head_only_counts_members():
    ms = [StageMatch("1", "1", 3, "completed", ("A", "B"), (2, 0)), StageMatch("2", "2", 3, "completed", ("A", "C"), (0, 2))]
    assert head_to_head(ms, ["A", "B"]) == {"A": 1}
