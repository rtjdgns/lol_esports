from dataclasses import replace

import pytest

from engine import knockout, swiss
from pipeline import aliases, knockout_view, normalize
from pipeline.swiss_data import load_knockouts, load_swiss
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


@pytest.fixture(scope="module")
def rules():
    return swiss.load_rules()


@pytest.fixture(scope="module")
def ko2025(conn):
    return load_knockouts(conn, "worlds_2025")[0]


def _cut(matches, completed_ids):
    return [m if m.match_id in completed_ids else replace(m, state="unstarted", wins=(0, 0)) for m in matches]


def test_bracket_structure_matches_2025(ko2025, rules):
    rounds = knockout.build_rounds(ko2025, rules["knockouts"]["round_sizes"])
    assert [len(r) for r in rounds] == [4, 2, 1]
    assert knockout.validate_bracket(rounds) == []


def test_finished_tournament_has_single_outcome(ko2025, rules):
    res = knockout.team_scenarios(ko2025, rules)
    assert res["total"] == 1
    champions = [t for t, s in res["teams"].items() if s["champion"]]
    assert len(champions) == 1 and res["teams"][champions[0]]["title"] == 1


def test_every_cut_point_keeps_actual_path_possible(ko2025, rules):
    chronological = [m.match_id for m in sorted(ko2025, key=lambda m: (m.start_time or "", int(m.match_id)))]
    final = [m for m in ko2025 if m.match_id == max(ko2025, key=lambda x: int(x.match_id)).match_id][0]
    champion = knockout.winner_of(final)
    full = knockout.build_rounds(ko2025, rules["knockouts"]["round_sizes"])
    for k in range(len(chronological) + 1):
        done = set(chronological[:k])
        res = knockout.team_scenarios(_cut(ko2025, done), rules)
        undecided = len(chronological) - k
        assert res["total"] == 2 ** undecided, k
        assert sum(s["title"] for s in res["teams"].values()) == res["total"]
        assert res["teams"][champion]["title"] > 0, k
        for r, rnd in enumerate(full):
            for j, m in enumerate(rnd):
                if m.match_id in done:
                    continue
                actual = set(m.team_ids)
                for t in actual:
                    others = actual - {t}
                    assert others <= res["teams"][t]["opponents"][r], (k, r, t)


def test_loser_marked_eliminated(ko2025, rules):
    res = knockout.team_scenarios(ko2025, rules)
    rounds = res["rounds"]
    for r, rnd in enumerate(rounds):
        for m in rnd:
            w = knockout.winner_of(m)
            for t in m.team_ids:
                if t != w:
                    assert res["teams"][t]["lost_in"] == r


def test_qf_draw_options_contain_actual_2025_pairing(conn, ko2025, rules):
    swiss_matches, _ = load_swiss(conn, "worlds_2025")
    teams = swiss.replay(swiss_matches)
    advanced = {t: (r.wins, r.losses) for t, r in teams.items() if swiss.classify(r.wins, r.losses) == "advanced"}
    options = knockout.qf_draw_options(advanced)
    assert len(options) == 18
    actual = frozenset(frozenset(m.team_ids) for m in knockout.build_rounds(ko2025, [4, 2, 1])[0])
    assert actual in options
    zero = [t for t, (w, l) in advanced.items() if l == 0]
    assert all(not any(frozenset((a, b)) in option for option in options) for a in zero for b in zero if a != b)


def test_qf_draw_options_rejects_unexpected_shape():
    assert knockout.qf_draw_options({"a": (3, 0)}) is None


def test_pre_draw_scenario_view_when_swiss_complete(conn, monkeypatch):
    real = knockout_view.load_knockouts

    def undrawn(c, slug):
        matches, names = real(c, slug)
        return [replace(m, team_ids=(None, None), state="unstarted", wins=(0, 0)) for m in matches], names

    monkeypatch.setattr(knockout_view, "load_knockouts", undrawn)
    text = "\n".join(knockout_view.render_scenario(conn, "worlds_2025"))
    assert "가능한 8강 추첨 결과 18가지" in text and "AL 3-0" in text


def test_views_for_2026_and_2025(conn):
    status = "\n".join(knockout_view.render_status(conn, "worlds_2025"))
    assert "우승: T1" in status and "검증 경고" not in status
    scen = "\n".join(knockout_view.render_scenario(conn, "worlds_2025"))
    assert "T1 · 우승" in scen
    assert "진출 확정 0/8팀" in "\n".join(knockout_view.render_scenario(conn, "worlds_2026"))
    assert "8강1 승자 vs 8강2 승자" in "\n".join(knockout_view.render_status(conn, "worlds_2026"))
