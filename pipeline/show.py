from engine.rules import load_event_rules
from engine.visibility import REASON_KO, evaluate_stage, load_policy, resolve_entry
from pipeline import follow
from pipeline.aliases import display_name
from pipeline.registry import STAGE_VIEWS
from pipeline.schedule_view import KST, parse_utc
from pipeline.visibility_data import build_contexts


def _match_line(conn, names, m):
    teams = " vs ".join(display_name(conn, t, names.get(t, "미정"), short=True) if t else "미정" for t in m.team_ids)
    when = parse_utc(m.start_time).astimezone(KST).strftime("%m-%d %H:%M") if m.start_time else "시각 미정"
    return f"{when} {teams}"


def render_show(conn, tournament, rules=None, policy=None, followed=None):
    rules = rules or load_event_rules(tournament)
    policy = policy or load_policy()
    followed = follow.followed_ids(conn) if followed is None else followed
    contexts = build_contexts(conn, tournament, rules, followed)
    lines = [f"[{tournament}] 공개 수준 정책으로 보기 (팔로우 {len(followed)}팀)"]
    for stage in rules["stages"]:
        ctx = contexts[stage["slug"]]
        ev = evaluate_stage(resolve_entry(policy, rules, stage), ctx)
        view = STAGE_VIEWS[stage["type"]]
        head = f"■ {stage['label']} · 수준 {ev['level']}"
        if ev["level"] > ev["base"]:
            head += f" (기본 {ev['base']}에서 승격: {', '.join(REASON_KO[r] for r in ev['stage_reasons'])})"
        lines += ["", head]
        lines += view.render_status(conn, tournament, stage, rules)
        if ev["level"] >= 2:
            lines += [""] + view.render_scenario(conn, tournament, stage, rules, None, None, ev["level"])
        elif ev["matches"]:
            by_id = {m.match_id: m for m in ctx["matches"]}
            lines.append("")
            lines.append("  경우의 수가 걸린 경기")
            team_ids = set()
            for mid, hit in sorted(ev["matches"].items(), key=lambda kv: (by_id[kv[0]].start_time or "", int(kv[0]))):
                m = by_id[mid]
                lines.append(f"  ▶ {_match_line(conn, ctx['names'], m)} — {', '.join(REASON_KO[r] for r in hit['reasons'])}")
                team_ids |= {t for t in m.team_ids if t}
            if team_ids:
                lines += [""] + view.render_scenario(conn, tournament, stage, rules, None, team_ids, 2)
    return lines
