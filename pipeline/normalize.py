import json
from collections import Counter

from storage.db import latest_raw_per_params, utc_now

SOURCE = "lolesports"


def _bodies(conn, endpoint):
    for row in latest_raw_per_params(conn, SOURCE, endpoint):
        yield row, json.loads(row["body_text"]), json.loads(row["params_json"])


def _tbd_team_id(value):
    return None if value in (None, "", "0") else value


def normalize_leagues(conn):
    out = {}
    for _, body, _ in _bodies(conn, "getLeagues"):
        for league in body["data"]["leagues"]:
            out[league["id"]] = league["slug"]
    return out


def normalize_tournaments(conn, league_slugs):
    n = 0
    for row, body, params in _bodies(conn, "getTournamentsForLeague"):
        league_id = params["leagueId"]
        for league in body["data"]["leagues"]:
            for t in league["tournaments"]:
                conn.execute(
                    "INSERT INTO tournaments (id, league_id, league_slug, slug, start_date, end_date, source_raw_id)"
                    " VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET league_id=excluded.league_id,"
                    " league_slug=excluded.league_slug, slug=excluded.slug, start_date=excluded.start_date,"
                    " end_date=excluded.end_date, source_raw_id=excluded.source_raw_id",
                    (t["id"], league_id, league_slugs.get(league_id), t["slug"], t.get("startDate"), t.get("endDate"), row["id"]),
                )
                n += 1
    return n


def normalize_teams(conn):
    n = 0
    for row, body, _ in _bodies(conn, "getTeams"):
        for t in body["data"]["teams"]:
            home = t.get("homeLeague") or {}
            conn.execute(
                "INSERT INTO teams (id, slug, code, name, status, home_league, home_region, image, source_raw_id)"
                " VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, code=excluded.code,"
                " name=excluded.name, status=excluded.status, home_league=excluded.home_league,"
                " home_region=excluded.home_region, image=excluded.image, source_raw_id=excluded.source_raw_id",
                (t["id"], t.get("slug"), t.get("code"), t.get("name"), t.get("status"),
                 home.get("name"), home.get("region"), t.get("image"), row["id"]),
            )
            n += 1
    return n


def _team_slot(team):
    result = team.get("result") or {}
    record = team.get("record") or {}
    return {
        "team_id": _tbd_team_id(team.get("id")),
        "code": team.get("code"),
        "name": team.get("name"),
        "game_wins": result.get("gameWins"),
        "outcome": result.get("outcome"),
        "record_wins": record.get("wins"),
        "record_losses": record.get("losses"),
    }


def collect_matches(conn):
    matches = {}
    links = set()
    stages = []
    for row, body, params in _bodies(conn, "getStandings"):
        for standing in body["data"]["standings"]:
            for stage in standing["stages"]:
                stages.append((stage["id"], params["tournamentId"], stage["slug"], stage.get("name"), row["id"]))
                for section in stage["sections"]:
                    for m in section["matches"]:
                        matches[m["id"]] = {
                            "tournament_id": params["tournamentId"],
                            "stage_id": stage["id"],
                            "state": m.get("state"),
                            "teams": [_team_slot(t) for t in m["teams"]],
                            "source_raw_id": row["id"],
                        }
                        for prev in m.get("previousMatchIds") or []:
                            links.add((m["id"], prev))
    for row, body, _ in _bodies(conn, "getSchedule"):
        for ev in body["data"]["schedule"]["events"]:
            m = ev.get("match")
            if ev.get("type") != "match" or not m:
                continue
            cur = matches.setdefault(m["id"], {"tournament_id": None, "stage_id": None, "teams": []})
            cur.update(
                block_name=ev.get("blockName"),
                start_time_utc=ev.get("startTime"),
                state=ev.get("state"),
                best_of=(m.get("strategy") or {}).get("count"),
                source_raw_id=row["id"],
            )
            sched_teams = [_team_slot(t) for t in m.get("teams", [])]
            if cur["teams"] and len(cur["teams"]) == len(sched_teams):
                for known, new in zip(cur["teams"], sched_teams):
                    known_id = known["team_id"]
                    known.update(new)
                    known["team_id"] = known_id
            else:
                cur["teams"] = sched_teams
    return matches, links, stages


def build_team_resolver(conn):
    by_pair = {}
    for r in conn.execute("SELECT id, code, name FROM teams"):
        by_pair.setdefault((r["code"], r["name"]), []).append(r["id"])
    return lambda code, name: by_pair[(code, name)][0] if len(by_pair.get((code, name), [])) == 1 else None


def normalize_matches(conn):
    matches, links, stages = collect_matches(conn)
    resolve = build_team_resolver(conn)
    now = utc_now()
    for st in stages:
        conn.execute(
            "INSERT INTO stages (id, tournament_id, slug, name, source_raw_id) VALUES (?,?,?,?,?)"
            " ON CONFLICT(id) DO UPDATE SET tournament_id=excluded.tournament_id, slug=excluded.slug,"
            " name=excluded.name, source_raw_id=excluded.source_raw_id", st)
    conn.execute("DELETE FROM match_links")
    for match_id, prev in links:
        conn.execute("INSERT INTO match_links (match_id, previous_match_id) VALUES (?,?)", (match_id, prev))
    unresolved = 0
    for match_id, m in matches.items():
        conn.execute(
            "INSERT INTO matches (id, tournament_id, stage_id, block_name, start_time_utc, state, best_of, source_raw_id, updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET tournament_id=excluded.tournament_id,"
            " stage_id=excluded.stage_id, block_name=excluded.block_name, start_time_utc=excluded.start_time_utc,"
            " state=excluded.state, best_of=excluded.best_of, source_raw_id=excluded.source_raw_id,"
            " updated_at=excluded.updated_at",
            (match_id, m.get("tournament_id"), m.get("stage_id"), m.get("block_name"), m.get("start_time_utc"),
             m.get("state"), m.get("best_of"), m.get("source_raw_id"), now),
        )
        conn.execute("DELETE FROM match_teams WHERE match_id=?", (match_id,))
        for slot, t in enumerate(m["teams"]):
            if t["team_id"] is None and t["code"] != "TBD":
                t["team_id"] = resolve(t["code"], t["name"])
                if t["team_id"] is None:
                    unresolved += 1
            conn.execute(
                "INSERT INTO match_teams (match_id, slot, team_id, code, name, game_wins, outcome, record_wins, record_losses)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (match_id, slot, t["team_id"], t["code"], t["name"], t["game_wins"], t["outcome"],
                 t["record_wins"], t["record_losses"]),
            )
    return len(matches), unresolved


def run(conn):
    league_slugs = normalize_leagues(conn)
    n_t = normalize_tournaments(conn, league_slugs)
    n_teams = normalize_teams(conn)
    n_m, unresolved = normalize_matches(conn)
    conn.commit()
    return {"tournaments": n_t, "teams": n_teams, "matches": n_m, "unresolved_team_slots": unresolved}


def report(conn):
    q = lambda sql: conn.execute(sql).fetchone()[0]
    return {
        "matches": q("SELECT COUNT(*) FROM matches"),
        "matches_without_tournament": q("SELECT COUNT(*) FROM matches WHERE tournament_id IS NULL"),
        "matches_without_best_of": q("SELECT COUNT(*) FROM matches WHERE best_of IS NULL"),
        "tbd_team_slots": q("SELECT COUNT(*) FROM match_teams WHERE team_id IS NULL AND code='TBD'"),
        "unresolved_team_slots": q("SELECT COUNT(*) FROM match_teams WHERE team_id IS NULL AND code<>'TBD'"),
        "team_ids_missing_in_teams": q(
            "SELECT COUNT(*) FROM match_teams mt LEFT JOIN teams t ON t.id=mt.team_id WHERE mt.team_id IS NOT NULL AND t.id IS NULL"),
        "states": dict(Counter(r[0] for r in conn.execute("SELECT state FROM matches"))),
    }
