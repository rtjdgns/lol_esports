from models.schema import Match


def wins_needed(best_of):
    return best_of // 2 + 1


def series_status(match: Match) -> str:
    a, b = match.teams
    need = wins_needed(match.best_of)
    header = f"{a.code} {a.game_wins} : {b.code} {b.game_wins}"
    if match.state == "unstarted":
        return f"{a.code} vs {b.code} · Bo{match.best_of}"
    if match.state == "completed":
        winner = a if a.game_wins > b.game_wins else b
        return f"{header} · {winner.code} 승"
    if match.best_of == 1:
        return f"{a.code} vs {b.code} · 단판 진행 중"
    if a.game_wins == b.game_wins == need - 1:
        return f"{header} · 마지막 세트"
    if a.game_wins == b.game_wins == 0:
        return f"{a.code} vs {b.code} · 1세트 진행 중"
    leader = a if a.game_wins > b.game_wins else b
    if a.game_wins == b.game_wins:
        return f"{header} · 각 {need - a.game_wins}승 남음"
    return f"{header} · {leader.code}팀 {need - leader.game_wins}승 남음"
