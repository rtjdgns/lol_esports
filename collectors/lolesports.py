import os

import requests

from models.schema import Match, SeriesTeam

BASE = "https://esports-api.lolesports.com/persisted/gw"


def parse_schedule_events(events):
    matches = []
    for ev in events:
        m = ev.get("match")
        if ev.get("type") != "match" or not m or len(m.get("teams", [])) != 2:
            continue
        teams = tuple(
            SeriesTeam(
                code=t["code"],
                name=t["name"],
                game_wins=(t.get("result") or {}).get("gameWins", 0),
                outcome=(t.get("result") or {}).get("outcome"),
                record_wins=(t.get("record") or {}).get("wins", 0),
                record_losses=(t.get("record") or {}).get("losses", 0),
            )
            for t in m["teams"]
        )
        matches.append(
            Match(
                match_id=m["id"],
                league_slug=ev["league"]["slug"],
                block_name=ev.get("blockName", ""),
                start_time=ev["startTime"],
                state=ev["state"],
                best_of=m["strategy"]["count"],
                teams=teams,
            )
        )
    return matches


class LolEsportsCollector:
    def __init__(self, api_key=None, hl="ko-KR"):
        key = api_key or os.environ.get("LOLESPORTS_API_KEY")
        if not key:
            raise RuntimeError("LOLESPORTS_API_KEY 필요")
        self.hl = hl
        self.session = requests.Session()
        self.session.headers["x-api-key"] = key

    def _get(self, endpoint, **params):
        resp = self.session.get(f"{BASE}/{endpoint}", params={"hl": self.hl, **params}, timeout=20)
        resp.raise_for_status()
        return resp.json()["data"]

    def league_id(self, slug):
        for league in self._get("getLeagues")["leagues"]:
            if league["slug"] == slug:
                return league["id"]
        raise KeyError(slug)

    def schedule(self, league_slug):
        data = self._get("getSchedule", leagueId=self.league_id(league_slug))
        return parse_schedule_events(data["schedule"]["events"])
