import json
from datetime import date, datetime, timezone

import pytest

from pipeline import aliases, normalize, schedule_view
from storage.db import connect
from tests.test_normalize import LEAGUE_ID, TOURNAMENT_ID, put


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


def test_alias_file_valid(conn):
    result = aliases.load_aliases(conn)
    assert result["unknown_team_id"] == []
    assert result["ambiguous_alias"] == []
    assert result["teams"] == 19


def test_alias_file_covers_worlds_entrants():
    data = json.loads(aliases.ALIASES_PATH.read_text(encoding="utf-8"))
    rules = json.loads((aliases.ALIASES_PATH.parent / "events" / "worlds_2026.json").read_text(encoding="utf-8"))
    entrants = set(rules["entrants"]["direct"]) | set(rules["entrants"]["play_in"])
    assert len(entrants) == 19
    assert entrants == {t["team_id"] for t in data["teams"]}


def test_resolve_alias(conn):
    aliases.load_aliases(conn)
    assert aliases.resolve_alias(conn, "젠지") == "100205573495116443"
    assert aliases.resolve_alias(conn, "gen.g") == "100205573495116443"
    assert aliases.resolve_alias(conn, "디플기") == "100725845018863243"
    assert aliases.resolve_alias(conn, "없는팀") is None


def test_display_name_falls_back_when_short_equals_full(conn):
    aliases.load_aliases(conn)
    assert aliases.display_name(conn, "100205576309502431", "FURIA", short=True) == "푸리아"
    assert aliases.display_name(conn, "98767991853197861", "T1", short=True) == "T1"
    assert aliases.display_name(conn, None, "TBD") == "미정"
    assert aliases.display_name(conn, "999", "Unknown Team") == "Unknown Team"


def test_today_view_uses_kst(conn):
    aliases.load_aliases(conn)
    rows = schedule_view.matches_between(conn, date(2026, 10, 16), 1)
    assert [r["start_time_utc"] for r in rows] == ["2026-10-15T18:00:00Z", "2026-10-15T23:00:00Z"]
    line = schedule_view.format_match(conn, rows[0])
    assert "10-16 03:00" in line and "클라우드9" in line
    assert schedule_view.kst_date(datetime(2026, 10, 15, 16, 0, tzinfo=timezone.utc)) == date(2026, 10, 16)


def test_follow_marks_and_filters(conn):
    from pipeline import follow
    aliases.load_aliases(conn)
    assert follow.add_follow(conn, "클라우드9") == "98767991877340524"
    assert follow.add_follow(conn, "없는팀") is None
    rows = schedule_view.matches_between(conn, date(2026, 10, 16), 2)
    follows = follow.followed_ids(conn)
    lines = [schedule_view.format_match(conn, m, follows) for m in rows]
    assert lines[0].startswith("★") and not lines[1].startswith("★")
    assert len(schedule_view.matches_between(conn, date(2026, 10, 16), 2, only_followed=True)) == 1
    follow.remove_follow(conn, "C9")
    assert follow.list_follows(conn) == []


def test_in_progress_line_shows_score(conn):
    conn.execute("UPDATE matches SET state='inProgress' WHERE start_time_utc='2026-10-15T23:00:00Z'")
    conn.execute("UPDATE match_teams SET game_wins=2 WHERE code='MVK' AND match_id=(SELECT id FROM matches WHERE start_time_utc='2026-10-15T23:00:00Z')")
    aliases.load_aliases(conn)
    rows = schedule_view.matches_between(conn, date(2026, 10, 16), 1)
    assert "푸리아 0 : MVK 2 · MVK팀 1승 남음" in schedule_view.format_match(conn, rows[1], set())
