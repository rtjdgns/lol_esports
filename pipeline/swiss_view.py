from collections import defaultdict

from engine.series import series_text
from engine.swiss import assign_rounds, classify, final_paths, load_rules, replay, team_scenarios, validate
from pipeline.aliases import display_name
from pipeline.schedule_view import KST, parse_utc
from pipeline.swiss_data import load_swiss

STATUS_KO = {"advanced": "진출 확정", "eliminated": "탈락 확정", "alive": "생존"}


def _name(conn, names, team_id):
    return display_name(conn, team_id, names.get(team_id, "미정"), short=True) if team_id else "미정"


def _when(m):
    return parse_utc(m.start_time).astimezone(KST).strftime("%m-%d %H:%M") if m.start_time else "시각 미정"


def _fmt_record(record):
    return f"{record[0]}-{record[1]}"


def render_status(conn, tournament_slug):
    rules = load_rules()
    matches, names = load_swiss(conn, tournament_slug)
    if not matches:
        return [f"{tournament_slug}: 스위스 경기 데이터 없음"]
    rounds = assign_rounds(matches, rules["swiss"]["round_sizes"])
    done = sum(1 for m in matches if m.state == "completed")
    live = sum(1 for m in matches if m.state == "inProgress")
    lines = [f"[{tournament_slug}] 스위스 진행 상태 — 완료 {done}/{len(matches)} · 진행 중 {live} · 예정 {len(matches) - done - live}"]
    for number in sorted(set(rounds.values())):
        group = sorted((m for m in matches if rounds[m.match_id] == number), key=lambda m: (m.start_time or "", int(m.match_id)))
        lines.append(f"\n{number}라운드")
        for m in group:
            a, b = (_name(conn, names, t) for t in m.team_ids)
            text = series_text(m.state, m.best_of, (a, b), m.wins) if m.best_of else f"{a} vs {b} · Bo?"
            lines.append(f"  {_when(m)}  {text}")
    teams = replay(matches)
    if done:
        lines.append("\n전적별 현황")
        groups = defaultdict(list)
        for t, rec in teams.items():
            groups[(rec.wins, rec.losses)].append(_name(conn, names, t))
        for record in sorted(groups, key=lambda r: (-r[0], r[1])):
            tag = STATUS_KO[classify(*record, rules["swiss"]["win_target"], rules["swiss"]["loss_limit"])]
            lines.append(f"  {_fmt_record(record)} {tag}: {', '.join(sorted(groups[record]))}")
    for issue in validate(matches, rounds, rules):
        lines.append(f"  ! 검증 경고: {issue}")
    return lines


def render_scenario(conn, tournament_slug, only_team=None):
    rules = load_rules()
    cfg = rules["swiss"]
    matches, names = load_swiss(conn, tournament_slug)
    scenarios = team_scenarios(matches, rules)
    lines = [f"[{tournament_slug}] 스위스 경우의 수 (경로 수는 가능한 승패 순서의 개수이며 확률이 아님)"]
    if not scenarios:
        paths = final_paths(0, 0, cfg["win_target"], cfg["loss_limit"])
        lines.append("  아직 대진이 확정된 경기가 없음. 1라운드는 티어 추첨(같은 지역 제외).")
        lines.append("  팀당 도달 가능한 최종 전적(0-0 기준): " + ", ".join(f"{_fmt_record(r)} {c}경로" for r, c in sorted(paths.items(), key=lambda x: (-x[0][0], x[0][1]))))
        return lines
    wanted = None
    if only_team:
        from pipeline.aliases import resolve_alias
        wanted = resolve_alias(conn, only_team)
        if wanted is None or wanted not in scenarios:
            return lines + [f"  '{only_team}' 팀을 이 대회에서 찾지 못함"]
    order = sorted(scenarios.items(), key=lambda kv: (-kv[1]["record"][0], kv[1]["record"][1], _name(conn, names, kv[0])))
    for team_id, s in order:
        if wanted and team_id != wanted:
            continue
        head = f"{_name(conn, names, team_id)} {_fmt_record(s['record'])} · {STATUS_KO[s['status']]}"
        if s["status"] != "alive":
            lines.append(head)
            continue
        paths = ", ".join(f"{_fmt_record(r)} {c}경로" for r, c in sorted(s["final_paths"].items(), key=lambda x: (-x[0][0], x[0][1])))
        lines.append(head + (" · 결정전" if s["decisive"] else ""))
        if s["match"] is not None:
            m = s["match"]
            opp = next(t for t in m.team_ids if t != team_id)
            lines.append(f"    이번 경기: {_when(m)} vs {_name(conn, names, opp)} · Bo{m.best_of or '?'}")
            for label, text in (("win", "이기면"), ("lose", "지면")):
                o = s["outcomes"][label]
                tail = STATUS_KO[o["status"]] if o["status"] != "alive" else "다음 라운드 후보 " + (", ".join(_name(conn, names, c) for c in o["candidates"]) or "미정")
                lines.append(f"    {text} {_fmt_record(o['record'])} → {tail}")
        elif s["waiting"] is not None:
            w = s["waiting"]
            lines.append(f"    다음 경기{'(결정전)' if w['decisive'] else ''} 후보 상대: " + (", ".join(_name(conn, names, c) for c in w["candidates"]) or "미정"))
        lines.append(f"    도달 가능 최종 전적: {paths}")
    return lines
