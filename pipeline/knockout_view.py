from engine import knockout
from engine.series import series_text
from engine.swiss import classify, replay
from pipeline.aliases import display_name, resolve_alias
from pipeline.schedule_view import KST, parse_utc
from pipeline.swiss_data import load_stage


def _name(conn, names, team_id):
    return display_name(conn, team_id, names.get(team_id, "미정"), short=True) if team_id else "미정"


def _when(m):
    return parse_utc(m.start_time).astimezone(KST).strftime("%m-%d %H:%M") if m.start_time else "시각 미정"


def _label(params, r, j):
    return f"{params['round_labels'][r]}{j + 1}"


def _slot_names(conn, names, params, rounds, r, j):
    m = rounds[r][j]
    if r == 0 or m.known():
        return tuple(_name(conn, names, t) for t in m.team_ids), m.wins
    slots = []
    for k, f in enumerate(knockout.feeders(rounds, r, j)):
        w = knockout.winner_of(f)
        slots.append(_name(conn, names, w) if w else f"{_label(params, r - 1, 2 * j + k)} 승자")
    return tuple(slots), (0, 0)


def render_status(conn, tournament_slug, stage, rules):
    params = stage["params"]
    matches, names = load_stage(conn, tournament_slug, stage["slug"])
    if not matches:
        return [f"{tournament_slug}: {stage['label']} 경기 데이터 없음"]
    rounds = knockout.build_rounds(matches, params["round_sizes"])
    done = sum(1 for m in matches if m.state == "completed")
    lines = [f"[{tournament_slug}] {stage['label']} 진행 상태 — 완료 {done}/{len(matches)}"]
    for r, rnd in enumerate(rounds):
        lines.append(f"\n{params['round_labels'][r]}")
        for j, m in enumerate(rnd):
            slot_names, wins = _slot_names(conn, names, params, rounds, r, j)
            text = series_text(m.state, m.best_of, slot_names, wins) if m.best_of else f"{slot_names[0]} vs {slot_names[1]} · Bo?"
            lines.append(f"  {_label(params, r, j)}  {_when(m)}  {text}")
    final = knockout.winner_of(rounds[-1][0])
    if final:
        lines.append(f"\n우승: {_name(conn, names, final)}")
    lines += [f"  ! 검증 경고: {i}" for i in knockout.validate_bracket(rounds)]
    return lines


def _pre_draw_lines(conn, tournament_slug, params, rules):
    swiss_stage = next((s for s in rules["stages"] if s["type"] == "swiss"), None)
    if params.get("draw") != "worlds_swiss_records" or swiss_stage is None:
        return ["  대진 추첨 전. 이 대회 규칙에는 추첨 전 계산 방식이 정의돼 있지 않음"]
    cfg = swiss_stage["params"]
    swiss, snames = load_stage(conn, tournament_slug, swiss_stage["slug"])
    teams = replay(swiss)
    advanced = {t: (r.wins, r.losses) for t, r in teams.items() if classify(r.wins, r.losses, cfg["win_target"], cfg["loss_limit"]) == "advanced"}
    lines = ["  8강 대진 추첨 전. 규칙: 스위스 3-0 두 팀은 3-2 팀을 상대로, 나머지 4팀은 서로 무작위."]
    if len(advanced) != 8:
        return lines + [f"  스위스 진행 중 — 진출 확정 {len(advanced)}/8팀. 8팀이 확정되면 가능한 추첨 결과를 계산합니다."]
    options = knockout.qf_draw_options(advanced)
    if options is None:
        return lines + ["  진출 팀 전적 구성이 예상(3-0 2팀·3-1 3팀·3-2 3팀)과 달라 계산하지 않음"]
    lines.append(f"  가능한 8강 추첨 결과 {len(options)}가지 (개수이며 확률이 아님)")
    for t, rec in sorted(advanced.items(), key=lambda kv: (-kv[1][0], kv[1][1])):
        opp = {}
        for option in options:
            for pair in option:
                if t in pair:
                    other = next(x for x in pair if x != t)
                    opp[other] = opp.get(other, 0) + 1
        detail = ", ".join(f"{_name(conn, snames, o)} {c}가지" for o, c in sorted(opp.items(), key=lambda kv: -kv[1]))
        lines.append(f"  {_name(conn, snames, t)} {rec[0]}-{rec[1]}: 8강 상대 후보 {detail}")
    return lines


def render_scenario(conn, tournament_slug, stage, rules, only_team=None, team_ids=None, level=3):
    params = stage["params"]
    matches, names = load_stage(conn, tournament_slug, stage["slug"])
    if not matches:
        return [f"{tournament_slug}: {stage['label']} 경기 데이터 없음"]
    result = knockout.team_scenarios(matches, params)
    header = f"[{tournament_slug}] {stage['label']} 경우의 수 (조합 수는 경기 결과의 가능한 개수이며 확률이 아님)"
    if not result["drawn"]:
        return [header] + _pre_draw_lines(conn, tournament_slug, params, rules)
    rounds, total = result["rounds"], result["total"]
    wanted = None
    if only_team:
        wanted = resolve_alias(conn, only_team)
        if wanted not in result["teams"]:
            return [header, f"  '{only_team}' 팀은 이 토너먼트에 없음"]
    lines = [header, f"  남은 결과 조합 {total}가지"]
    labels = params["round_labels"]

    def order(item):
        t, s = item
        return (not s["champion"], s["lost_in"] is not None, -s["title"], _name(conn, names, t))

    for team_id, s in sorted(result["teams"].items(), key=order):
        if wanted and team_id != wanted:
            continue
        if team_ids is not None and team_id not in team_ids:
            continue
        name = _name(conn, names, team_id)
        if s["champion"]:
            lines.append(f"{name} · 우승")
            continue
        if s["lost_in"] is not None:
            lines.append(f"{name} · {labels[s['lost_in']]} 탈락")
            continue
        lines.append(f"{name} · 생존 · 우승으로 이어지는 조합 {s['title']}/{total}" if level >= 3 else f"{name} · 생존")
        shown = 0
        for r in range(len(rounds)):
            played = any(m.state == "completed" and team_id in m.team_ids for m in rounds[r])
            if played or not s["opponents"][r]:
                continue
            if level < 3 and shown:
                break
            shown += 1
            opp = sorted(_name(conn, names, o) for o in s["opponents"][r])
            tag = "상대 확정" if len(opp) == 1 else "상대 후보"
            lines.append(f"    {labels[r]} {tag}: {', '.join(opp)}")
    return lines
