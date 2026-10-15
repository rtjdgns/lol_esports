import json
import re
from pathlib import Path

ALIASES_PATH = Path(__file__).resolve().parent.parent / "rules" / "team_aliases.json"


def norm(text):
    return re.sub(r"[\s.\-_'’]+", "", text).casefold()


def load_aliases(conn, path=ALIASES_PATH):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    known = {r["id"] for r in conn.execute("SELECT id FROM teams")}
    problems = {"unknown_team_id": [], "ambiguous_alias": []}
    owners = {}
    rows = []
    for t in data["teams"]:
        if t["team_id"] not in known:
            problems["unknown_team_id"].append(t["team_id"])
            continue
        entries = [(t["ko"], "ko"), (t["ko_short"], "ko_short"), (t["en"], "en")]
        entries += [(a, "alt") for a in t.get("aliases", [])]
        for alias, kind in entries:
            key = norm(alias)
            owners.setdefault(key, set()).add(t["team_id"])
            rows.append((t["team_id"], alias, key, kind))
    for key, ids in owners.items():
        if len(ids) > 1:
            problems["ambiguous_alias"].append(key)
    conn.execute("DELETE FROM team_aliases")
    for row in rows:
        conn.execute("INSERT OR IGNORE INTO team_aliases (team_id, alias, alias_norm, kind) VALUES (?,?,?,?)", row)
    conn.commit()
    return {"teams": len(data["teams"]), "alias_rows": len(rows), **problems}


def resolve_alias(conn, text):
    rows = conn.execute("SELECT DISTINCT team_id FROM team_aliases WHERE alias_norm=?", (norm(text),)).fetchall()
    return rows[0]["team_id"] if len(rows) == 1 else None


def display_name(conn, team_id, fallback, short=False):
    if team_id is None:
        return "미정" if fallback in (None, "TBD") else fallback
    order = ("ko_short", "ko") if short else ("ko", "ko_short")
    row = conn.execute(
        "SELECT alias FROM team_aliases WHERE team_id=? AND kind IN ('ko','ko_short')"
        " ORDER BY CASE kind WHEN ? THEN 0 ELSE 1 END LIMIT 1",
        (team_id, order[0]),
    ).fetchone()
    return row["alias"] if row else fallback
