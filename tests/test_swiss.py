from dataclasses import replace

import pytest

from engine import swiss
from pipeline import aliases, normalize, swiss_view
from pipeline.swiss_data import load_swiss
from storage.db import connect
from tests.test_normalize import LEAGUE_ID, put

T2025 = "113475452383887518"
T2026 = "115660540725177488"


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


@pytest.fixture(scope="module")
def rules():
    return swiss.load_rules()


@pytest.fixture(scope="module")
def m2025(conn):
    return load_swiss(conn, "worlds_2025")[0]


def test_replay_2025_matches_rule_model(m2025, rules):
    rounds = swiss.assign_rounds(m2025, rules["swiss"]["round_sizes"])
    assert len(m2025) == 33
    assert swiss.validate(m2025, rounds, rules) == []


def test_2025_final_records(m2025):
    teams = swiss.replay(m2025)
    from collections import Counter
    finals = Counter((t.wins, t.losses) for t in teams.values())
    assert finals == {(3, 0): 2, (3, 1): 3, (3, 2): 3, (2, 3): 3, (1, 3): 3, (0, 3): 2}


def test_final_paths_from_start():
    assert swiss.final_paths(0, 0) == {(3, 0): 1, (3, 1): 3, (3, 2): 6, (2, 3): 6, (1, 3): 3, (0, 3): 1}
    assert swiss.final_paths(2, 2) == {(3, 2): 1, (2, 3): 1}
    assert swiss.final_paths(3, 1) == {(3, 1): 1}


def _truncate(matches, rounds, before_round, pending_round=None):
    out = []
    for m in matches:
        r = rounds[m.match_id]
        if r < before_round:
            out.append(m)
        elif pending_round is not None and r == pending_round:
            out.append(replace(m, state="unstarted", wins=(0, 0)))
    return out


def _opponent_in_round(matches, rounds, team, round_no):
    for m in matches:
        if rounds[m.match_id] == round_no and team in m.team_ids:
            return next(t for t in m.team_ids if t != team)
    return None


def test_candidates_contain_actual_next_opponent_when_waiting(m2025, rules):
    rounds = swiss.assign_rounds(m2025, rules["swiss"]["round_sizes"])
    for r in range(2, 6):
        history = _truncate(m2025, rounds, r)
        scen = swiss.team_scenarios(history, rules)
        for m in m2025:
            if rounds[m.match_id] != r:
                continue
            a, b = m.team_ids
            assert b in scen[a]["waiting"]["candidates"], (r, a, b)
            assert a in scen[b]["waiting"]["candidates"], (r, b, a)


def test_candidates_contain_actual_next_opponent_mid_round(m2025, rules):
    rounds = swiss.assign_rounds(m2025, rules["swiss"]["round_sizes"])
    by_id = {m.match_id: m for m in m2025}
    for r in range(1, 5):
        history = _truncate(m2025, rounds, r, pending_round=r)
        scen = swiss.team_scenarios(history, rules)
        for m in m2025:
            if rounds[m.match_id] != r:
                continue
            for idx, team in enumerate(m.team_ids):
                won = m.wins[idx] > m.wins[1 - idx]
                outcome = scen[team]["outcomes"]["win" if won else "lose"]
                nxt = _opponent_in_round(m2025, rounds, team, r + 1)
                if nxt is None:
                    assert outcome["status"] != "alive"
                else:
                    assert nxt in outcome["candidates"], (r, team, nxt)


def test_current_opponent_never_a_next_candidate(m2025, rules):
    rounds = swiss.assign_rounds(m2025, rules["swiss"]["round_sizes"])
    for r in range(1, 5):
        history = _truncate(m2025, rounds, r, pending_round=r)
        scen = swiss.team_scenarios(history, rules)
        for m in history:
            if m.state != "unstarted":
                continue
            a, b = m.team_ids
            for x, y in ((a, b), (b, a)):
                for outcome in scen[x]["outcomes"].values():
                    assert y not in outcome["candidates"], (r, x, y)


def test_decisive_flag_matches_best_of(m2025, rules):
    rounds = swiss.assign_rounds(m2025, rules["swiss"]["round_sizes"])
    history = _truncate(m2025, rounds, 3, pending_round=3)
    scen = swiss.team_scenarios(history, rules)
    for m in history:
        if m.state != "unstarted":
            continue
        for t in m.team_ids:
            assert scen[t]["decisive"] == (m.best_of == 3)


def test_2026_before_draw_has_schedule_but_no_teams(conn, rules):
    matches, _ = load_swiss(conn, "worlds_2026")
    assert len(matches) == 33
    assert swiss.team_scenarios(matches, rules) == {}
    rounds = swiss.assign_rounds(matches, rules["swiss"]["round_sizes"])
    assert [sum(1 for v in rounds.values() if v == n) for n in range(1, 6)] == [8, 8, 8, 6, 3]


def test_views_render(conn):
    status = "\n".join(swiss_view.render_status(conn, "worlds_2025"))
    assert "전적별 현황" in status and "검증 경고" not in status
    scen = "\n".join(swiss_view.render_scenario(conn, "worlds_2026"))
    assert "1경로" in scen and "6경로" in scen
    assert "젠지 3-1 · 진출 확정" in "\n".join(swiss_view.render_scenario(conn, "worlds_2025", "젠지"))
