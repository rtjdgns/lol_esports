from engine.types import StageMatch


def load_stage(conn, tournament_slug, stage_slug):
    rows = conn.execute(
        "SELECT m.id, m.start_time_utc, m.best_of, m.state,"
        " a.team_id AS a_id, b.team_id AS b_id, a.game_wins AS a_w, b.game_wins AS b_w,"
        " a.name AS a_name, b.name AS b_name"
        " FROM matches m JOIN stages s ON s.id=m.stage_id JOIN tournaments t ON t.id=m.tournament_id"
        " JOIN match_teams a ON a.match_id=m.id AND a.slot=0 JOIN match_teams b ON b.match_id=m.id AND b.slot=1"
        " WHERE t.slug=? AND s.slug=?",
        (tournament_slug, stage_slug),
    ).fetchall()
    matches, names = [], {}
    for r in rows:
        matches.append(StageMatch(r["id"], r["start_time_utc"], r["best_of"], r["state"],
                                  (r["a_id"], r["b_id"]), (r["a_w"] or 0, r["b_w"] or 0)))
        if r["a_id"]:
            names[r["a_id"]] = r["a_name"]
        if r["b_id"]:
            names[r["b_id"]] = r["b_name"]
    return matches, names


def load_swiss(conn, tournament_slug):
    return load_stage(conn, tournament_slug, "swiss")


def load_knockouts(conn, tournament_slug):
    return load_stage(conn, tournament_slug, "knockouts")
