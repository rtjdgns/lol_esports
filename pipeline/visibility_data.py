from engine import elimination, knockout, swiss
from pipeline.swiss_data import load_stage


def _swiss_advanced(conn, tournament, rules):
    stage = next((s for s in rules["stages"] if s["type"] == "swiss"), None)
    if stage is None:
        return None
    matches, _ = load_stage(conn, tournament, stage["slug"])
    p = stage["params"]
    teams = swiss.replay(matches)
    return {t for t, r in teams.items() if swiss.classify(r.wins, r.losses, p["win_target"], p["loss_limit"]) == "advanced"}


def build_contexts(conn, tournament, rules, followed):
    contexts = {}
    for stage in rules["stages"]:
        matches, names = load_stage(conn, tournament, stage["slug"])
        p, kind = stage["params"], stage["type"]
        info = {}
        draw_done = pre_draw_ready = None
        if matches and kind == "swiss":
            mc = swiss.match_contexts(matches, p)
            for m in matches:
                info[m.match_id] = {"teams": m.team_ids, "state": m.state, "decisive": mc[m.match_id]["decisive"], "last_round": mc[m.match_id]["last_round"]}
        elif matches and kind == "bracket_graph":
            try:
                by_role = elimination.order_roles(matches, p["roles"], p["order"])
            except ValueError:
                by_role = {}
            eliminating = set(elimination.eliminating_roles(p["slots"]))
            for role, m in by_role.items():
                info[m.match_id] = {"teams": m.team_ids, "state": m.state, "decisive": role in eliminating or role == p["advance_from"], "last_round": role == p["advance_from"]}
        elif matches and kind == "single_elim":
            try:
                rounds = knockout.build_rounds(matches, p["round_sizes"])
            except ValueError:
                rounds = []
            for r, rnd in enumerate(rounds):
                for m in rnd:
                    info[m.match_id] = {"teams": m.team_ids, "state": m.state, "decisive": True, "last_round": r == len(rounds) - 1}
            if rounds:
                draw_done = all(m.known() for m in rounds[0])
                if p.get("draw") == "worlds_swiss_records":
                    advanced = _swiss_advanced(conn, tournament, rules)
                    pre_draw_ready = (not draw_done) and advanced is not None and len(advanced) == 8
        contexts[stage["slug"]] = {
            "matches": matches, "names": names, "followed": set(followed), "match_info": info,
            "participants": {t for m in matches for t in m.team_ids if t},
            "draw_done": draw_done, "pre_draw_ready": pre_draw_ready}
    return contexts
