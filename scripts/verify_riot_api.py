import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://esports-api.lolesports.com/persisted/gw"
LIVE_BASE = "https://esports-api.lolesports.com/persisted/gw"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw_samples"
RATE_HEADERS = ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


def call(session, endpoint, params, save_as):
    started = time.time()
    resp = session.get(f"{BASE}/{endpoint}", params=params, timeout=20)
    elapsed = time.time() - started
    rate = {h: resp.headers[h] for h in RATE_HEADERS if h in resp.headers}
    print(f"[{resp.status_code}] {endpoint} {params} {elapsed:.2f}s rate_headers={rate or '없음'}")
    body = None
    try:
        body = resp.json()
    except ValueError:
        print("  JSON 아님:", resp.text[:200])
    if body is not None:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{save_as}.json").write_text(
            json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return resp.status_code, body


def key_paths(obj, prefix="", depth=0, max_depth=6, out=None):
    out = set() if out is None else out
    if depth > max_depth:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else k
            out.add(path)
            key_paths(v, path, depth + 1, max_depth, out)
    elif isinstance(obj, list):
        for item in obj[:5]:
            key_paths(item, prefix + "[]", depth + 1, max_depth, out)
    return out


def print_fields(title, body, needles):
    paths = key_paths(body)
    print(f"  {title}: 필드 경로 {len(paths)}개")
    for needle in needles:
        hits = sorted(p for p in paths if needle.lower() in p.lower())
        print(f"    '{needle}': {hits[:6] if hits else '없음'}")


def main():
    parser = argparse.ArgumentParser(description="lolesports API 응답 구조 검증")
    parser.add_argument("--league", default="worlds", help="getLeagues 의 slug (기본 worlds)")
    parser.add_argument("--hl", default="ko-KR")
    parser.add_argument("--no-key", action="store_true", help="키 없이 호출해 인증 필요 여부만 확인")
    args = parser.parse_args()

    api_key = os.environ.get("LOLESPORTS_API_KEY")
    if not api_key and not args.no_key:
        sys.exit("환경변수 LOLESPORTS_API_KEY 가 필요하다. .env.example 참고.")

    session = requests.Session()
    if not args.no_key:
        session.headers["x-api-key"] = api_key
    hl = {"hl": args.hl}

    status, leagues = call(session, "getLeagues", hl, "getLeagues")
    if status != 200 or args.no_key:
        return
    league = next((x for x in leagues["data"]["leagues"] if x["slug"] == args.league), None)
    if not league:
        sys.exit(f"slug '{args.league}' 리그 없음")
    league_id = league["id"]
    print(f"리그: {league['name']} id={league_id}")

    status, tours = call(session, "getTournamentsForLeague", {**hl, "leagueId": league_id}, "getTournamentsForLeague")
    tournaments = tours["data"]["leagues"][0]["tournaments"] if status == 200 else []
    print_fields("tournaments", tours, ["startDate", "endDate", "stage", "section"])

    status, sched = call(session, "getSchedule", {**hl, "leagueId": league_id}, "getSchedule")
    events = sched["data"]["schedule"]["events"] if status == 200 else []
    print(f"  events {len(events)}개, pages={sched['data']['schedule'].get('pages')}")
    print_fields("getSchedule", sched, ["strategy", "count", "result.gameWins", "blockName", "state", "record", "outcome"])

    if tournaments:
        tid = tournaments[0]["id"]
        for t in tournaments:
            status, st = call(session, "getStandings", {**hl, "tournamentId": t["id"]}, f"getStandings_{t['id']}")
            if status == 200:
                print_fields("getStandings", st, ["stages", "sections", "rankings", "ordinal", "record", "wins"])
                tid = t["id"]
                break

    status, live = call(session, "getLive", hl, "getLive")
    print_fields("getLive", live, ["strategy", "count", "state", "id"])

    match_id = next((e["match"]["id"] for e in events if e.get("match")), None)
    if match_id:
        call(session, "getEventDetails", {**hl, "id": match_id}, "getEventDetails")

    status, teams = call(session, "getTeams", hl, "getTeams")
    if status == 200:
        print_fields("getTeams", teams, ["players", "role", "summonerName", "homeLeague"])

    status, done = call(session, "getCompletedEvents", {**hl, "tournamentId": tid} if tournaments else hl, "getCompletedEvents")


if __name__ == "__main__":
    main()
