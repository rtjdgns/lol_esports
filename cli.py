import argparse
import sys

from collectors.lolesports import LolEsportsCollector
from datetime import date

from pipeline import aliases, follow, knockout_view, normalize, playin_view, schedule_view, swiss_view

VIEWS = {"play_in": playin_view, "swiss": swiss_view, "knockouts": knockout_view}
from storage.db import DEFAULT_DB, connect, list_raw


def parse_kv(items):
    out = {}
    for item in items or []:
        key, _, value = item.partition("=")
        if not key or not _:
            sys.exit(f"-p 형식은 key=value: {item}")
        out[key] = value
    return out


def cmd_fetch(args):
    conn = connect(args.db)
    collector = LolEsportsCollector(hl=args.hl)
    row_id, raw = collector.fetch_and_store(conn, args.endpoint, **parse_kv(args.param))
    print(f"saved id={row_id} status={raw.status_code} bytes={len(raw.body_text)} params={raw.params}")
    if raw.status_code != 200:
        sys.exit(1)


def cmd_list(args):
    conn = connect(args.db)
    for r in list_raw(conn, args.limit):
        print(f"{r['id']:>4} {r['fetched_at']} {r['status_code']} {r['endpoint']:<24} {r['bytes']:>8}B {r['sha']} {r['params_json']}")


def cmd_normalize(args):
    conn = connect(args.db)
    print("normalized:", normalize.run(conn))
    for key, value in normalize.report(conn).items():
        print(f"  {key}: {value}")


def cmd_aliases(args):
    conn = connect(args.db)
    result = aliases.load_aliases(conn)
    print(result)
    if result["unknown_team_id"] or result["ambiguous_alias"]:
        sys.exit(1)


def cmd_today(args):
    conn = connect(args.db)
    start = date.fromisoformat(args.date) if args.date else schedule_view.kst_date()
    rows = schedule_view.matches_between(conn, start, args.days, only_followed=args.followed)
    print(f"{start} (KST) 부터 {args.days}일, {len(rows)}경기")
    follows = follow.followed_ids(conn)
    for m in rows:
        print(" ", schedule_view.format_match(conn, m, follows))


def cmd_follow(args):
    conn = connect(args.db)
    if args.action == "list":
        print("팔로우:", ", ".join(follow.list_follows(conn)) or "없음")
        return
    fn = follow.add_follow if args.action == "add" else follow.remove_follow
    for name in args.names:
        print(f"{name}: {'적용' if fn(conn, name) else '팀을 찾지 못함(별칭 확인)'}")


def cmd_status(args):
    conn = connect(args.db)
    print("\n".join(VIEWS[args.stage].render_status(conn, args.tournament)))


def cmd_scenario(args):
    conn = connect(args.db)
    print("\n".join(VIEWS[args.stage].render_scenario(conn, args.tournament, args.team)))


def main():
    parser = argparse.ArgumentParser(prog="cli")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="엔드포인트 호출 결과를 raw_responses에 저장")
    f.add_argument("endpoint")
    f.add_argument("-p", "--param", action="append", help="key=value (반복 가능)")
    f.add_argument("--hl", default="ko-KR")
    f.set_defaults(func=cmd_fetch)

    l = sub.add_parser("list", help="저장된 raw 응답 목록")
    l.add_argument("--limit", type=int, default=20)
    l.set_defaults(func=cmd_list)

    n = sub.add_parser("normalize", help="저장된 raw 최신본을 정규화 테이블로 변환(재실행해도 동일 결과)")
    n.set_defaults(func=cmd_normalize)

    a = sub.add_parser("aliases", help="rules/team_aliases.json을 DB에 적재하고 검증")
    a.set_defaults(func=cmd_aliases)

    d = sub.add_parser("today", help="KST 기준 경기 목록")
    d.add_argument("--date", help="YYYY-MM-DD (기본: 오늘 KST)")
    d.add_argument("--days", type=int, default=1)
    d.add_argument("--followed", action="store_true", help="팔로우한 팀 경기만")
    d.set_defaults(func=cmd_today)

    fo = sub.add_parser("follow", help="팀 팔로우 관리")
    fo.add_argument("action", choices=["add", "remove", "list"])
    fo.add_argument("names", nargs="*")
    fo.set_defaults(func=cmd_follow)

    st = sub.add_parser("status", help="현재 대회 진행 상태(일정·결과·전적). 경우의 수는 scenario")
    st.add_argument("stage", choices=list(VIEWS))
    st.add_argument("--tournament", default="worlds_2026")
    st.set_defaults(func=cmd_status)

    sc = sub.add_parser("scenario", help="경우의 수(결정전, 이기면/지면, 다음 상대 후보, 최종 전적)")
    sc.add_argument("stage", choices=list(VIEWS))
    sc.add_argument("--tournament", default="worlds_2026")
    sc.add_argument("--team", help="팀 별칭(예: 젠지)")
    sc.set_defaults(func=cmd_scenario)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
