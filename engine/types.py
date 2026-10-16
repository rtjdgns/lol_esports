from dataclasses import dataclass


@dataclass(frozen=True)
class StageMatch:
    match_id: str
    start_time: object
    best_of: object
    state: str
    team_ids: tuple
    wins: tuple

    def known(self):
        return None not in self.team_ids
