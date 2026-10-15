import argparse
import sys

from collectors.lolesports import LolEsportsCollector
from datetime import date

from pipeline import aliases, normalize, schedule_view
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
    rows = schedule_view.matches_between(conn, start, args.days)
    print(f"{start} (KST) 부터 {args.days}일, {len(rows)}경기")
    for m in rows:
        print(" ", schedule_view.format_match(conn, m))


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
    d.set_defaults(func=cmd_today)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
