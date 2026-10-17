import json
import os

import requests

from models.schema import Match, SeriesTeam
from storage.db import RawResponse, save_raw, utc_now

BASE = "https://esports-api.lolesports.com/persisted/gw"
SOURCE = "lolesports"


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
    def __init__(self, api_key=None, hl="ko-KR", session=None):
        key = api_key or os.environ.get("LOLESPORTS_API_KEY")
        if not key:
            raise RuntimeError("LOLESPORTS_API_KEY 필요")
        self.hl = hl
        self.session = session or requests.Session()
        self.session.headers["x-api-key"] = key

    def fetch_raw(self, endpoint, **params) -> RawResponse:
        full = {"hl": self.hl, **params}
        resp = self.session.get(f"{BASE}/{endpoint}", params=full, timeout=20)
        return RawResponse(SOURCE, endpoint, full, utc_now(), resp.status_code, resp.text)

    def fetch_and_store(self, conn, endpoint, **params):
        raw = self.fetch_raw(endpoint, **params)
        return save_raw(conn, raw), raw

    def fetch_schedule_history(self, conn, league_id, since, max_pages=40):
        saved, token = 0, None
        for _ in range(max_pages):
            params = {"leagueId": league_id}
            if token:
                params["pageToken"] = token
            _, raw = self.fetch_and_store(conn, "getSchedule", **params)
            saved += 1
            if raw.status_code != 200:
                break
            schedule = json.loads(raw.body_text)["data"]["schedule"]
            events = schedule.get("events", [])
            token = (schedule.get("pages") or {}).get("older")
            if not token or (events and min(e["startTime"] for e in events) < since):
                break
        return saved
