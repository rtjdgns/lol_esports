from datetime import datetime, timedelta, timezone

from engine.series import series_text
from pipeline.aliases import display_name
from pipeline.follow import followed_ids

KST = timezone(timedelta(hours=9))


def parse_utc(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def kst_date(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(KST).date()


def match_teams(conn, match_id):
    return conn.execute("SELECT * FROM match_teams WHERE match_id=? ORDER BY slot", (match_id,)).fetchall()


def matches_between(conn, start_date, days=1, only_followed=False):
    start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=KST).astimezone(timezone.utc)
    end = start + timedelta(days=days)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    rows = conn.execute(
        "SELECT m.*, s.slug AS stage_slug, t.slug AS tournament_slug FROM matches m"
        " LEFT JOIN stages s ON s.id=m.stage_id LEFT JOIN tournaments t ON t.id=m.tournament_id"
        " WHERE m.start_time_utc >= ? AND m.start_time_utc < ? ORDER BY m.start_time_utc, m.id",
        (start.strftime(fmt), end.strftime(fmt)),
    ).fetchall()
    if only_followed:
        follows = followed_ids(conn)
        rows = [m for m in rows if any(t["team_id"] in follows for t in match_teams(conn, m["id"]))]
    return rows


def format_match(conn, m, follows=None):
    follows = followed_ids(conn) if follows is None else follows
    teams = match_teams(conn, m["id"])
    names = tuple(display_name(conn, t["team_id"], t["name"], short=True) for t in teams)
    wins = tuple(t["game_wins"] or 0 for t in teams)
    when = parse_utc(m["start_time_utc"]).astimezone(KST).strftime("%m-%d %H:%M")
    mark = "★" if any(t["team_id"] in follows for t in teams) else " "
    text = series_text(m["state"], m["best_of"] or 0, names, wins) if m["best_of"] else f"{names[0]} vs {names[1]} · Bo?"
    return f"{mark} {when} {m['block_name'] or ''} {text}"
