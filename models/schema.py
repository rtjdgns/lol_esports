from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SeriesTeam:
    code: str
    name: str
    game_wins: int = 0
    outcome: Optional[str] = None
    record_wins: int = 0
    record_losses: int = 0


@dataclass(frozen=True)
class Match:
    match_id: str
    league_slug: str
    block_name: str
    start_time: str
    state: str
    best_of: int
    teams: tuple = field(default_factory=tuple)
