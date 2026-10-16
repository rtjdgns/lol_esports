from engine.rules import RulesError, get_stage, load_event_rules
from pipeline import knockout_view, playin_view, swiss_view

STAGE_VIEWS = {"swiss": swiss_view, "single_elim": knockout_view, "bracket_graph": playin_view}


def render(conn, tournament_slug, kind, stage_slug=None, team=None, rules=None):
    rules = rules or load_event_rules(tournament_slug)
    stages = [get_stage(rules, stage_slug)] if stage_slug else rules["stages"]
    out = []
    for i, stage in enumerate(stages):
        view = STAGE_VIEWS[stage["type"]]
        if kind == "status":
            lines = view.render_status(conn, tournament_slug, stage, rules)
        elif kind == "scenario":
            lines = view.render_scenario(conn, tournament_slug, stage, rules, team)
        else:
            raise RulesError(f"알 수 없는 종류: {kind}")
        if i:
            out.append("")
        out += lines
    return out
