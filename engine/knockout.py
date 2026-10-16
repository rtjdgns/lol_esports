from itertools import permutations

from engine.types import StageMatch


def build_rounds(matches, round_sizes):
    if len(matches) != sum(round_sizes):
        raise ValueError(f"토너먼트 경기 수 {len(matches)} 가 구조 {round_sizes} 와 다름")
    ordered = sorted(matches, key=lambda m: int(m.match_id))
    rounds, index = [], 0
    for size in round_sizes:
        rounds.append(ordered[index:index + size])
        index += size
    return rounds


def feeders(rounds, r, j):
    return rounds[r - 1][2 * j], rounds[r - 1][2 * j + 1]


def winner_of(m):
    if m.state != "completed" or not m.known():
        return None
    return m.team_ids[0] if m.wins[0] > m.wins[1] else m.team_ids[1]


def validate_bracket(rounds):
    issues = []
    for r in range(1, len(rounds)):
        for j, m in enumerate(rounds[r]):
            decided = [winner_of(f) for f in feeders(rounds, r, j) if winner_of(f)]
            if decided and m.known() and not set(decided) <= set(m.team_ids):
                issues.append(f"{m.match_id}: 이전 라운드 승자 {decided} 가 참가 팀 {m.team_ids} 에 없음")
    return issues


def enumerate_outcomes(rounds):
    if any(not m.known() for m in rounds[0]):
        return None
    flat = [(r, j, m) for r, rnd in enumerate(rounds) for j, m in enumerate(rnd)]
    outcomes = []

    def walk(index, winners):
        if index == len(flat):
            outcomes.append(dict(winners))
            return
        r, j, m = flat[index]
        if r == 0:
            participants = m.team_ids
        else:
            participants = tuple(winners[f.match_id] for f in feeders(rounds, r, j))
        fixed = winner_of(m)
        options = (fixed,) if fixed in participants else participants
        for w in options:
            winners[m.match_id] = w
            walk(index + 1, winners)
        winners.pop(m.match_id, None)

    walk(0, {})
    return outcomes


def team_scenarios(matches, params):
    if params["wiring"] != "adjacent_pairs":
        raise NotImplementedError(params["wiring"])
    sizes = params["round_sizes"]
    rounds = build_rounds(matches, sizes)
    issues = validate_bracket(rounds)
    outcomes = enumerate_outcomes(rounds)
    if outcomes is None:
        return {"drawn": False, "rounds": rounds, "issues": issues, "teams": {}, "total": 0}
    teams = {}
    for t in {t for m in rounds[0] for t in m.team_ids}:
        teams[t] = {"title": 0, "opponents": [set() for _ in rounds], "reach": [0] * len(rounds), "lost_in": None, "champion": False}
    for outcome in outcomes:
        for r, rnd in enumerate(rounds):
            for j, m in enumerate(rnd):
                participants = m.team_ids if r == 0 else tuple(outcome[f.match_id] for f in feeders(rounds, r, j))
                for p in participants:
                    teams[p]["reach"][r] += 1
                    teams[p]["opponents"][r].update(x for x in participants if x != p)
        teams[outcome[rounds[-1][0].match_id]]["title"] += 1
    for r, rnd in enumerate(rounds):
        for j, m in enumerate(rnd):
            w = winner_of(m)
            if w is None:
                continue
            for p in m.team_ids:
                if p != w:
                    teams[p]["lost_in"] = r
    final_winner = winner_of(rounds[-1][0])
    if final_winner:
        teams[final_winner]["champion"] = True
    return {"drawn": True, "rounds": rounds, "issues": issues, "teams": teams, "total": len(outcomes)}


def perfect_matchings(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for i, other in enumerate(rest):
        for tail in perfect_matchings(rest[:i] + rest[i + 1:]):
            yield [frozenset((first, other))] + tail


def qf_draw_options(records):
    zero = [t for t, (w, l) in records.items() if l == 0]
    two = [t for t, (w, l) in records.items() if l == 2]
    if len(records) != 8 or len(zero) != 2 or len(two) != 3:
        return None
    options = []
    for chosen in permutations(two, len(zero)):
        pairs = [frozenset((z, c)) for z, c in zip(zero, chosen)]
        remaining = [t for t in records if t not in zero and t not in chosen]
        for rest in perfect_matchings(remaining):
            options.append(frozenset(pairs + rest))
    return options
