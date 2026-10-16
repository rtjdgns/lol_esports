from pipeline.aliases import display_name, resolve_alias
from storage.db import utc_now


def add_follow(conn, text):
    team_id = resolve_alias(conn, text)
    if team_id is None:
        return None
    conn.execute("INSERT OR IGNORE INTO follows (team_id, created_at) VALUES (?, ?)", (team_id, utc_now()))
    conn.commit()
    return team_id


def remove_follow(conn, text):
    team_id = resolve_alias(conn, text)
    if team_id is None:
        return None
    conn.execute("DELETE FROM follows WHERE team_id=?", (team_id,))
    conn.commit()
    return team_id


def followed_ids(conn):
    return {r["team_id"] for r in conn.execute("SELECT team_id FROM follows")}


def list_follows(conn):
    return [display_name(conn, team_id, team_id) for team_id in sorted(followed_ids(conn))]
