from engine.types import StageMatch


def order_roles(matches, roles, order="start_time"):
    if order != "start_time":
        raise NotImplementedError(order)
    if len(matches) != len(roles):
        raise ValueError(f"경기 수 {len(matches)} 가 구조 {len(roles)} 와 다름")
    ordered = sorted(matches, key=lambda m: (m.start_time or "", int(m.match_id)))
    return dict(zip(roles, ordered))


def winner_of(m):
    if m.state != "completed" or not m.known():
        return None
    return m.team_ids[0] if m.wins[0] > m.wins[1] else m.team_ids[1]


def loser_of(m):
    w = winner_of(m)
    return None if w is None else (m.team_ids[1] if w == m.team_ids[0] else m.team_ids[0])


def resolve(src, winners, losers):
    kind, role = src.split(":")
    return winners[role] if kind == "W" else losers[role]


def eliminating_roles(slots):
    referenced = {s.split(":")[1] for srcs in slots.values() for s in srcs if s.startswith("L:")}
    return [role for role in slots if role not in referenced]


def validate(by_role, slots):
    issues = []
    winners = {r: winner_of(m) for r, m in by_role.items()}
    losers = {r: loser_of(m) for r, m in by_role.items()}
    for role, srcs in slots.items():
        m = by_role[role]
        if not m.known():
            continue
        for src in srcs:
            if src == "seed":
                continue
            kind, ref = src.split(":")
            expected = winners[ref] if kind == "W" else losers[ref]
            if expected is not None and expected not in m.team_ids:
                issues.append(f"{role}: {ref}의 {'승자' if kind == 'W' else '패자'} {expected} 가 참가 팀 {m.team_ids} 에 없음")
    return issues


def enumerate_outcomes(by_role, roles, slots):
    if any(slots[r] == ["seed", "seed"] and not by_role[r].known() for r in roles):
        return None
    outcomes = []

    def walk(index, winners, losers, participants):
        if index == len(roles):
            outcomes.append({"winners": dict(winners), "losers": dict(losers), "participants": dict(participants)})
            return
        role = roles[index]
        m = by_role[role]
        if slots[role] == ["seed", "seed"]:
            pair = tuple(m.team_ids)
        else:
            pair = tuple(resolve(s, winners, losers) for s in slots[role])
        participants[role] = pair
        fixed = winner_of(m)
        options = (fixed,) if fixed in pair else pair
        for w in options:
            winners[role] = w
            losers[role] = pair[1] if w == pair[0] else pair[0]
            walk(index + 1, winners, losers, participants)
        winners.pop(role, None)
        losers.pop(role, None)
        participants.pop(role, None)

    walk(0, {}, {}, {})
    return outcomes


def team_scenarios(matches, cfg):
    roles, slots = cfg["roles"], cfg["slots"]
    by_role = order_roles(matches, roles, cfg["order"])
    issues = validate(by_role, slots)
    outcomes = enumerate_outcomes(by_role, roles, slots)
    if outcomes is None:
        return {"known": False, "by_role": by_role, "issues": issues, "teams": {}, "total": 0}
    out_roles = set(eliminating_roles(slots))
    teams = {}
    for t in {t for r in roles if slots[r] == ["seed", "seed"] for t in by_role[r].team_ids}:
        teams[t] = {"advance": 0, "opponents": {r: set() for r in roles}, "certain": {r: True for r in roles}, "status": "alive", "eliminated_in": None}
    for o in outcomes:
        for role in roles:
            pair = o["participants"][role]
            for t in teams:
                if t in pair:
                    teams[t]["opponents"][role].update(x for x in pair if x != t)
                else:
                    teams[t]["certain"][role] = False
        teams[o["winners"][cfg["advance_from"]]]["advance"] += 1
    for role in roles:
        m = by_role[role]
        w, l = winner_of(m), loser_of(m)
        if l is not None and role in out_roles:
            teams[l]["status"] = "eliminated"
            teams[l]["eliminated_in"] = role
        if w is not None and role == cfg["advance_from"]:
            teams[w]["status"] = "advanced"
    for t, s in teams.items():
        s["next_role"] = None
        if s["status"] == "alive":
            for role in roles:
                if by_role[role].state != "completed" and s["certain"][role]:
                    s["next_role"] = role
                    break
        s["lose_eliminates"] = s["next_role"] in out_roles if s["next_role"] else None
    return {"known": True, "by_role": by_role, "issues": issues, "teams": teams, "total": len(outcomes), "out_roles": out_roles}
