import json
from itertools import product
from pathlib import Path

import pytest

from engine import elimination
from engine.rules import load_event_rules, stage_params
from engine.types import StageMatch
from pipeline import aliases, normalize, registry
from storage.db import connect

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "play_in_20261016.json"


@pytest.fixture(scope="module")
def cfg():
    return stage_params(load_event_rules("worlds_2026"), "play_ins")


def build(cfg, bits, completed, seeds=("A", "B", "C", "D")):
    roles, slots = cfg["roles"], cfg["slots"]
    winners, losers, matches = {}, {}, []
    for i, role in enumerate(roles):
        if role == "r1a":
            pair = (seeds[0], seeds[1])
        elif role == "r1b":
            pair = (seeds[2], seeds[3])
        else:
            pair = tuple((winners if s.startswith("W") else losers)[s.split(":")[1]] for s in slots[role])
        first_wins = bits[i]
        winners[role] = pair[0] if first_wins else pair[1]
        losers[role] = pair[1] if first_wins else pair[0]
        done = i < completed
        wins = ((3, 1) if first_wins else (1, 3)) if done else (0, 0)
        mid = str(900 - i * 7) if i < 2 else str(100 + i)
        matches.append(StageMatch(mid, f"2026-10-{15 + i // 2:02d}T{18 + (i % 2) * 5:02d}:00:00Z", 5, "completed" if done else "unstarted",
                                  pair if (done or i < 2) else (None, None), wins))
    return matches, winners[cfg["advance_from"]]


def test_all_results_all_cut_points(cfg):
    for bits in product((True, False), repeat=6):
        for completed in range(7):
            matches, champion = build(cfg, bits, completed)
            res = elimination.team_scenarios(matches, cfg)
            assert res["known"] and res["issues"] == []
            assert res["total"] == 2 ** (6 - completed), (bits, completed)
            assert sum(s["advance"] for s in res["teams"].values()) == res["total"]
            assert res["teams"][champion]["advance"] > 0
            advanced = [t for t, s in res["teams"].items() if s["status"] == "advanced"]
            assert advanced == ([champion] if completed == 6 else [])


def test_elimination_rules_derived_from_graph(cfg):
    assert set(elimination.eliminating_roles(cfg["slots"])) == {"lb_r1", "lb_final", "final"}


def test_each_team_eliminated_after_second_loss(cfg):
    for bits in product((True, False), repeat=6):
        matches, _ = build(cfg, bits, 6)
        res = elimination.team_scenarios(matches, cfg)
        statuses = sorted(s["status"] for s in res["teams"].values())
        assert statuses == ["advanced", "eliminated", "eliminated", "eliminated"]


def test_ids_do_not_drive_wiring(cfg):
    matches, _ = build(cfg, (True,) * 6, 2)
    ids = [int(m.match_id) for m in matches]
    assert ids[0] > ids[1]
    assert sorted(range(6), key=lambda i: ids[i]) != list(range(6))
    assert elimination.team_scenarios(matches, cfg)["issues"] == []


def test_validate_flags_wrong_team(cfg):
    matches, _ = build(cfg, (True,) * 6, 2)
    bad = list(matches)
    bad[2] = StageMatch(bad[2].match_id, bad[2].start_time, 5, "unstarted", ("A", "B"), (0, 0))
    issues = elimination.team_scenarios(bad, cfg)["issues"]
    assert len(issues) == 1 and "wb_final" in issues[0]


def test_real_snapshot_20261016(cfg):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))["matches"]
    matches = [StageMatch(r["id"], r["start_time_utc"], r["best_of"], r["state"], (r["at_"], r["bt"]), (r["aw"] or 0, r["bw"] or 0)) for r in data]
    res = elimination.team_scenarios(matches, cfg)
    assert res["issues"] == [] and res["total"] == 16
    by_code = {}
    for r in data:
        by_code[r["at_"]] = r["ac"]
        by_code[r["bt"]] = r["bc"]
    adv = {by_code[t]: s["advance"] for t, s in res["teams"].items() if t in by_code}
    assert adv == {"KC": 6, "MVK": 6, "C9": 2, "FUR": 2}
    c9 = next(t for t, c in by_code.items() if c == "C9")
    assert res["teams"][c9]["next_role"] == "lb_r1" and res["teams"][c9]["lose_eliminates"] is True


def test_views_render_from_db():
    c = connect(":memory:")
    from tests.test_normalize import LEAGUE_ID, put
    from tests.test_swiss import T2026
    put(c, "getLeagues", "getLeagues.json")
    put(c, "getTournamentsForLeague", "getTournamentsForLeague.json", leagueId=LEAGUE_ID)
    put(c, "getTeams", "getTeams.json")
    put(c, "getSchedule", "getSchedule.json", leagueId=LEAGUE_ID)
    put(c, "getStandings", f"getStandings_{T2026}.json", tournamentId=T2026)
    normalize.run(c)
    aliases.load_aliases(c)
    status = "\n".join(registry.render(c, "worlds_2026", "status", "play_ins"))
    assert "승자조 결승" in status and "검증 경고" not in status
    assert "1라운드 대진 미확정" not in "\n".join(registry.render(c, "worlds_2026", "scenario", "play_ins"))
