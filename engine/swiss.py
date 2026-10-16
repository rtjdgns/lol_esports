import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from engine.types import StageMatch

RULES_PATH = Path(__file__).resolve().parent.parent / "rules" / "worlds_2026.json"


def load_rules(path=RULES_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


SwissMatch = StageMatch


def sort_key(m):
    return (m.start_time or "", int(m.match_id))


def assign_rounds(matches, round_sizes):
    rounds = {}
    ordered = sorted(matches, key=sort_key)
    index = 0
    for number, size in enumerate(round_sizes, 1):
        for m in ordered[index:index + size]:
            rounds[m.match_id] = number
        index += size
    for m in ordered[index:]:
        rounds[m.match_id] = len(round_sizes) + 1
    return rounds


@dataclass
class TeamRecord:
    team_id: str
    wins: int = 0
    losses: int = 0

    def __post_init__(self):
        self.faced = set()

    @property
    def played(self):
        return self.wins + self.losses


def replay(matches, team_ids=()):
    teams = {t: TeamRecord(t) for t in team_ids}
    for m in sorted(matches, key=sort_key):
        for t in m.team_ids:
            if t is not None:
                teams.setdefault(t, TeamRecord(t))
        if m.state != "completed" or not m.known():
            continue
        a, b = m.team_ids
        winner, loser = (a, b) if m.wins[0] > m.wins[1] else (b, a)
        teams[winner].wins += 1
        teams[loser].losses += 1
        teams[a].faced.add(b)
        teams[b].faced.add(a)
    return teams


def classify(wins, losses, win_target=3, loss_limit=3):
    if wins >= win_target:
        return "advanced"
    if losses >= loss_limit:
        return "eliminated"
    return "alive"


def is_decisive(wins, losses, win_target=3, loss_limit=3):
    return wins == win_target - 1 or losses == loss_limit - 1


def final_paths(wins, losses, win_target=3, loss_limit=3):
    if wins >= win_target or losses >= loss_limit:
        return {(wins, losses): 1}
    out = Counter()
    for nxt in ((wins + 1, losses), (wins, losses + 1)):
        for record, count in final_paths(*nxt, win_target, loss_limit).items():
            out[record] += count
    return dict(out)


def validate(matches, rounds, rules):
    issues = []
    teams = {}
    met = set()
    decisive_bo = rules["swiss"]["best_of"]
    for m in sorted(matches, key=sort_key):
        if not m.known():
            continue
        a, b = m.team_ids
        ra, rb = teams.setdefault(a, [0, 0]), teams.setdefault(b, [0, 0])
        if ra != rb:
            issues.append(f"{m.match_id}: 경기 시작 시 두 팀 전적이 다름 {ra} {rb}")
        if rounds.get(m.match_id) != ra[0] + ra[1] + 1:
            issues.append(f"{m.match_id}: 라운드 배정 {rounds.get(m.match_id)} 와 전적 기반 {ra[0] + ra[1] + 1} 불일치")
        pair = frozenset((a, b))
        if pair in met:
            issues.append(f"{m.match_id}: 재대결")
        met.add(pair)
        expected = decisive_bo["decisive"] if is_decisive(*ra) else decisive_bo["normal"]
        if m.best_of is not None and m.best_of != expected:
            issues.append(f"{m.match_id}: Bo{m.best_of} (규칙상 Bo{expected})")
        if m.state == "completed":
            winner, loser = (a, b) if m.wins[0] > m.wins[1] else (b, a)
            teams[winner][0] += 1
            teams[loser][1] += 1
    return issues


def _pending_by_team(matches):
    pending = {}
    for m in matches:
        if m.state != "completed" and m.known():
            for t in m.team_ids:
                pending[t] = m
    return pending


def next_opponent_candidates(team_id, record_after, games_after, teams, pending, exclude=()):
    out = []
    me = teams[team_id]
    for other_id, other in teams.items():
        if other_id == team_id or other_id in me.faced or other_id in exclude:
            continue
        if other.played == games_after and (other.wins, other.losses) == record_after:
            out.append(other_id)
        elif other.played == games_after - 1 and other_id in pending:
            if (other.wins + 1, other.losses) == record_after or (other.wins, other.losses + 1) == record_after:
                out.append(other_id)
    return sorted(out)


def team_scenarios(matches, rules, team_ids=()):
    cfg = rules["swiss"]
    target, limit = cfg["win_target"], cfg["loss_limit"]
    teams = replay(matches, team_ids)
    pending = _pending_by_team(matches)
    result = {}
    for team_id, rec in teams.items():
        status = classify(rec.wins, rec.losses, target, limit)
        entry = {"record": (rec.wins, rec.losses), "status": status, "match": None, "outcomes": {}, "waiting": None, "final_paths": {}}
        if status == "alive":
            entry["final_paths"] = final_paths(rec.wins, rec.losses, target, limit)
            entry["decisive"] = is_decisive(rec.wins, rec.losses, target, limit)
            match = pending.get(team_id)
            if match is not None:
                entry["match"] = match
                current_opponent = next(x for x in match.team_ids if x != team_id)
                for label, nxt in (("win", (rec.wins + 1, rec.losses)), ("lose", (rec.wins, rec.losses + 1))):
                    st = classify(*nxt, target, limit)
                    cands = next_opponent_candidates(team_id, nxt, rec.played + 1, teams, pending, exclude=(current_opponent,)) if st == "alive" else []
                    entry["outcomes"][label] = {"record": nxt, "status": st, "candidates": cands}
            elif rec.played > 0:
                entry["waiting"] = {
                    "candidates": next_opponent_candidates(team_id, (rec.wins, rec.losses), rec.played, teams, pending),
                    "decisive": is_decisive(rec.wins, rec.losses, target, limit),
                }
        result[team_id] = entry
    return result
