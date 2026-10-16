from models.schema import Match


def wins_needed(best_of):
    return best_of // 2 + 1


def series_text(state, best_of, names, wins):
    a, b = names
    wa, wb = wins
    need = wins_needed(best_of)
    header = f"{a} {wa} : {b} {wb}"
    if state == "unstarted":
        return f"{a} vs {b} · Bo{best_of}"
    if state == "completed":
        return f"{header} · {a if wa > wb else b} 승"
    if best_of == 1:
        return f"{a} vs {b} · 단판 진행 중"
    if wa == wb == need - 1:
        return f"{header} · 마지막 세트"
    if wa == wb == 0:
        return f"{a} vs {b} · 1세트 진행 중"
    if wa == wb:
        return f"{header} · 각 {need - wa}승 남음"
    leader, lw = (a, wa) if wa > wb else (b, wb)
    return f"{header} · {leader}팀 {need - lw}승 남음"


def series_status(match: Match) -> str:
    a, b = match.teams
    return series_text(match.state, match.best_of, (a.code, b.code), (a.game_wins, b.game_wins))
