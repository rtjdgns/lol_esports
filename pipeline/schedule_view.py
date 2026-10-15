from datetime import datetime, timedelta, timezone

from pipeline.aliases import display_name

KST = timezone(timedelta(hours=9))
STATE_KO = {"unstarted": "예정", "completed": "종료"}


def parse_utc(text):
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def kst_date(now=None):
    return (now or datetime.now(timezone.utc)).astimezone(KST).date()


def matches_between(conn, start_date, days=1):
    start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=KST).astimezone(timezone.utc)
    end = start + timedelta(days=days)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return conn.execute(
        "SELECT m.*, s.slug AS stage_slug, t.slug AS tournament_slug FROM matches m"
        " LEFT JOIN stages s ON s.id=m.stage_id LEFT JOIN tournaments t ON t.id=m.tournament_id"
        " WHERE m.start_time_utc >= ? AND m.start_time_utc < ? ORDER BY m.start_time_utc, m.id",
        (start.strftime(fmt), end.strftime(fmt)),
    ).fetchall()


def format_match(conn, m):
    teams = conn.execute("SELECT * FROM match_teams WHERE match_id=? ORDER BY slot", (m["id"],)).fetchall()
    names = [display_name(conn, t["team_id"], t["name"], short=True) for t in teams]
    when = parse_utc(m["start_time_utc"]).astimezone(KST).strftime("%m-%d %H:%M")
    bo = f"Bo{m['best_of']}" if m["best_of"] else "Bo?"
    state = STATE_KO.get(m["state"], "진행 중")
    if m["state"] == "completed" and len(teams) == 2:
        score = f"{teams[0]['game_wins']} : {teams[1]['game_wins']}"
        return f"{when} {m['block_name'] or ''} {names[0]} {score} {names[1]} · {bo} · {state}"
    return f"{when} {m['block_name'] or ''} {names[0]} vs {names[1]} · {bo} · {state}"
