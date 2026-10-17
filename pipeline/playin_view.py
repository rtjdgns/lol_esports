from engine import elimination
from engine.series import series_text
from pipeline.aliases import display_name, resolve_alias
from pipeline.schedule_view import KST, parse_utc
from pipeline.swiss_data import load_stage


def _name(conn, names, team_id):
    return display_name(conn, team_id, names.get(team_id, "미정"), short=True) if team_id else "미정"


def _when(m):
    return parse_utc(m.start_time).astimezone(KST).strftime("%m-%d %H:%M") if m.start_time else "시각 미정"


def _slot_names(conn, names, cfg, by_role, role):
    m = by_role[role]
    if m.known():
        return tuple(_name(conn, names, t) for t in m.team_ids), m.wins
    out = []
    winners = {r: elimination.winner_of(x) for r, x in by_role.items()}
    losers = {r: elimination.loser_of(x) for r, x in by_role.items()}
    for src in cfg["slots"][role]:
        if src == "seed":
            out.append("미정")
            continue
        kind, ref = src.split(":")
        decided = winners[ref] if kind == "W" else losers[ref]
        out.append(_name(conn, names, decided) if decided else f"{cfg['labels'][ref]} {'승자' if kind == 'W' else '패자'}")
    return tuple(out), (0, 0)


def render_status(conn, tournament_slug, stage, rules):
    cfg = stage["params"]
    matches, names = load_stage(conn, tournament_slug, stage["slug"])
    if not matches:
        return [f"{tournament_slug}: 플레이-인 경기 데이터 없음"]
    try:
        by_role = elimination.order_roles(matches, cfg["roles"], cfg["order"])
    except ValueError as e:
        return [f"{tournament_slug}: 플레이-인 구조와 맞지 않음 ({e})"]
    done = sum(1 for m in matches if m.state == "completed")
    lines = [f"[{tournament_slug}] 플레이-인 진행 상태 — 완료 {done}/{len(matches)}"]
    for role in cfg["roles"]:
        m = by_role[role]
        slot_names, wins = _slot_names(conn, names, cfg, by_role, role)
        text = series_text(m.state, m.best_of, slot_names, wins) if m.best_of else f"{slot_names[0]} vs {slot_names[1]} · Bo?"
        lines.append(f"  {cfg['labels'][role]:<8} {_when(m)}  {text}")
    final = elimination.winner_of(by_role[cfg["advance_from"]])
    if final:
        lines.append(f"\n스위스 진출: {_name(conn, names, final)}")
    lines += [f"  ! 검증 경고: {i}" for i in elimination.validate(by_role, cfg["slots"])]
    return lines


def render_scenario(conn, tournament_slug, stage, rules, only_team=None, team_ids=None, level=2):
    cfg = stage["params"]
    matches, names = load_stage(conn, tournament_slug, stage["slug"])
    if not matches:
        return [f"{tournament_slug}: 플레이-인 경기 데이터 없음"]
    res = elimination.team_scenarios(matches, cfg)
    header = f"[{tournament_slug}] 플레이-인 경우의 수 (조합 수는 경기 결과의 가능한 개수이며 확률이 아님)"
    if not res["known"]:
        return [header, "  1라운드 대진 미확정"]
    wanted = None
    if only_team:
        wanted = resolve_alias(conn, only_team)
        if wanted not in res["teams"]:
            return [header, f"  '{only_team}' 팀은 플레이-인에 없음"]
    labels = cfg["labels"]
    lines = [header, f"  남은 결과 조합 {res['total']}가지 · 결승 승자 1팀이 스위스 진출"]
    order = sorted(res["teams"].items(), key=lambda kv: (kv[1]["status"] == "eliminated", kv[1]["status"] != "advanced", -kv[1]["advance"], _name(conn, names, kv[0])))
    for t, s in order:
        if wanted and t != wanted:
            continue
        if team_ids is not None and t not in team_ids:
            continue
        name = _name(conn, names, t)
        if s["status"] == "advanced":
            lines.append(f"{name} · 스위스 진출 확정")
            continue
        if s["status"] == "eliminated":
            lines.append(f"{name} · 탈락 ({labels[s['eliminated_in']]})")
            continue
        lines.append(f"{name} · 생존 · 스위스 진출로 이어지는 조합 {s['advance']}/{res['total']}")
        nr = s["next_role"]
        if nr:
            opp = ", ".join(sorted(_name(conn, names, o) for o in s["opponents"][nr]))
            tail = "패하면 탈락" if s["lose_eliminates"] else "패하면 패자조로"
            if nr == cfg["advance_from"]:
                tail = "이기면 스위스 진출, " + tail
            lines.append(f"    다음 경기 {labels[nr]} 상대 {opp} · {tail}")
        for role in cfg["roles"]:
            if role == nr or res["by_role"][role].state == "completed" or not s["opponents"][role]:
                continue
            if nr and cfg["roles"].index(role) < cfg["roles"].index(nr):
                continue
            opp = ", ".join(sorted(_name(conn, names, o) for o in s["opponents"][role]))
            lines.append(f"    {labels[role]} 상대 후보: {opp}")
    lines += [f"  ! 검증 경고: {i}" for i in res["issues"]]
    return lines
