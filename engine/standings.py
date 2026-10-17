from collections import Counter, defaultdict
from dataclasses import dataclass

from engine.swiss import sort_key


@dataclass
class TeamRow:
    team_id: str
    wins: int = 0
    losses: int = 0
    set_wins: int = 0
    set_losses: int = 0

    @property
    def set_diff(self):
        return self.set_wins - self.set_losses

    @property
    def played(self):
        return self.wins + self.losses


def derive_rounds(matches, offset=0):
    seen, out = Counter(), {}
    for m in sorted(matches, key=sort_key):
        if not m.known():
            out[m.match_id] = None
            continue
        pair = frozenset(m.team_ids)
        seen[pair] += 1
        out[m.match_id] = offset + seen[pair]
    return out


def _completed(matches):
    return [m for m in matches if m.state == "completed" and m.known()]


def tally(matches, teams=None):
    rows = {t: TeamRow(t) for t in (teams or ())}
    for m in _completed(matches):
        a, b = m.team_ids
        for t in (a, b):
            if teams is None:
                rows.setdefault(t, TeamRow(t))
        wa, wb = m.wins
        for t, mine, theirs in ((a, wa, wb), (b, wb, wa)):
            if t not in rows:
                continue
            rows[t].set_wins += mine
            rows[t].set_losses += theirs
            if mine > theirs:
                rows[t].wins += 1
            else:
                rows[t].losses += 1
    return rows


def head_to_head(matches, members):
    members = set(members)
    wins = Counter()
    for m in _completed(matches):
        a, b = m.team_ids
        if a in members and b in members:
            wins[a if m.wins[0] > m.wins[1] else b] += 1
    return wins


TIEBREAKERS = {"set_diff", "head_to_head", "decider_match"}


def split_deciders(matches, regular_rounds):
    rounds = derive_rounds(matches)
    regular, deciders = [], []
    for m in matches:
        r = rounds.get(m.match_id)
        (deciders if r is not None and r > regular_rounds else regular).append(m)
    return regular, deciders


def _split(group, key):
    buckets = defaultdict(list)
    for t in group:
        buckets[key(t)].append(t)
    return [buckets[k] for k in sorted(buckets, reverse=True)]


def rank(matches, teams=None, tiebreakers=("set_diff", "head_to_head", "decider_match"), deciders=()):
    unknown = set(tiebreakers) - TIEBREAKERS
    if unknown:
        raise ValueError(f"지원하지 않는 동률 기준: {sorted(unknown)}")
    rows = tally(matches, teams)
    groups = _split(list(rows), lambda t: (rows[t].wins, -rows[t].losses))
    ordered, unresolved = [], []
    for group in groups:
        pending = [group]
        for tb in tiebreakers:
            nxt = []
            for g in pending:
                if len(g) == 1:
                    nxt.append(g)
                    continue
                if tb == "set_diff":
                    nxt.extend(_split(g, lambda t: rows[t].set_diff))
                elif tb == "head_to_head":
                    h = head_to_head(matches, g)
                    nxt.extend(_split(g, lambda t: h[t]))
                else:
                    h = head_to_head(deciders, g)
                    nxt.extend(_split(g, lambda t: h[t]))
            pending = nxt
        for g in pending:
            if len(g) > 1:
                unresolved.append(sorted(g))
            ordered.extend(sorted(g))
    return [rows[t] for t in ordered], unresolved
