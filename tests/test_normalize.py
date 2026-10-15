import json
from pathlib import Path

import pytest

from pipeline import normalize
from storage.db import RawResponse, connect, save_raw

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "raw_samples"
LEAGUE_ID = "98767975604431411"
TOURNAMENT_ID = "115660540725177488"


def put(conn, endpoint, filename, **params):
    save_raw(conn, RawResponse("lolesports", endpoint, {"hl": "ko-KR", **params}, "2026-10-15T00:00:00Z", 200,
                               (SAMPLES / filename).read_text(encoding="utf-8")))


@pytest.fixture
def conn():
    c = connect(":memory:")
    put(c, "getLeagues", "getLeagues.json")
    put(c, "getTournamentsForLeague", "getTournamentsForLeague.json", leagueId=LEAGUE_ID)
    put(c, "getTeams", "getTeams.json")
    put(c, "getSchedule", "getSchedule.json", leagueId=LEAGUE_ID)
    put(c, "getStandings", f"getStandings_{TOURNAMENT_ID}.json", tournamentId=TOURNAMENT_ID)
    normalize.run(c)
    return c


def snapshot(c):
    return {t: [tuple(r) for r in c.execute(f"SELECT * FROM {t} ORDER BY 1,2")]
            for t in ("tournaments", "stages", "teams", "match_teams")}


def test_counts_and_integrity(conn):
    rep = normalize.report(conn)
    assert rep["unresolved_team_slots"] == 0
    assert rep["team_ids_missing_in_teams"] == 0
    assert conn.execute("SELECT league_slug FROM tournaments WHERE slug='worlds_2026'").fetchone()[0] == "worlds"


def test_rerun_is_idempotent(conn):
    before = snapshot(conn)
    count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    normalize.run(conn)
    assert snapshot(conn) == before
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == count


def test_tbd_stored_as_null_team(conn):
    rows = conn.execute("SELECT team_id, code FROM match_teams WHERE code='TBD'").fetchall()
    assert rows and all(r["team_id"] is None for r in rows)


def test_stage_slug_and_best_of_merge(conn):
    row = conn.execute(
        "SELECT s.slug AS stage, m.best_of, m.tournament_id FROM matches m JOIN stages s ON s.id=m.stage_id"
        " WHERE m.best_of=5 AND s.slug='play_ins' LIMIT 1").fetchone()
    assert row["tournament_id"] == TOURNAMENT_ID


def test_team_ids_come_from_standings(conn):
    row = conn.execute(
        "SELECT team_id FROM match_teams WHERE code='C9' AND team_id IS NOT NULL LIMIT 1").fetchone()
    assert row["team_id"] == "98767991877340524"
