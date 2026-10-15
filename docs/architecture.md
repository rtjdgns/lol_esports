# 구조 설명

## 데이터 흐름
collectors(소스별 어댑터) → models(공통 스키마) → engine(계산) → notifier(후속 단계)

## 모듈
- `models/schema.py`: `Match`, `SeriesTeam`. 소스와 무관한 공통 형태. Standing, RosterEntry는 getStandings `rankings` 형식 확인 후 추가한다.
- `collectors/lolesports.py`: Riot lolesports API 어댑터. `parse_schedule_events`는 네트워크 없이 원본 응답 dict를 변환하므로 `data/raw_samples/`로 테스트한다. 보조 소스를 붙일 때 같은 `Match` 리스트를 반환하는 클래스를 추가한다.
- `engine/series.py`: 시리즈 상황 문구. 확정 승수는 `Bo // 2 + 1`, 남은 승수는 확정 승수에서 현재 승수를 뺀 값이다.
- `engine/swiss.py`: 스위스 팀 상태(진출/탈락 확정, 필요 승수, 결정전). 규칙 수치는 `rules/worlds_2026.json`에서 읽는다.
- `rules/`: 수동 입력 규칙 파일. 각 파일에 출처와 검증일, 미확인 항목을 기록한다.

## 주의
- 진행 중 상태 값을 `unstarted`/`completed` 외에는 모두 진행 중으로 처리한다. 실제 값(`inProgress` 추정)은 경기 중 getLive로 확인 필요.
- 스위스 상태 판정은 현재 전적 기준 확정/탈락과 필요 승수까지다. 남은 대진을 고려한 조건부 판정은 대진 매칭 규칙 구현 후 다음 단계.
- 스위스 진출/탈락 결정전의 Bo3 여부와 타이브레이커는 공식 프라이머에 없거나 모호하다(미확인).

## 실행
```
pip install -r requirements.txt
python -m pytest
```

## 2단계 진행 (2a: 원본 저장)
- `storage/db.py`: SQLite 연결과 `raw_responses` 테이블(source, endpoint, params_json, fetched_at, status_code, body_text, body_sha256). 호출마다 행을 추가하고 덮어쓰지 않는다. 같은 응답이어도 행은 남고 `body_sha256`으로 변경 여부를 비교한다. 오류 응답(403 등)도 저장하되 `latest_raw`는 200만 반환한다.
- `collectors/lolesports.py`: `fetch_raw`(호출만), `fetch_and_store`(호출 후 저장). 변환은 별도 함수라 저장된 본문으로 다시 돌릴 수 있다.
- `cli.py`: `python cli.py fetch <endpoint> -p key=value`, `python cli.py list`. DB 위치는 `data/lol_esports.db`(git 제외), `--db`로 변경.
- 같은 응답을 계속 쌓으면 용량이 늘어난다. 보관 정책(오래된 행 삭제 또는 동일 해시 생략)은 스케줄러(5단계)를 붙일 때 정한다.

## 2단계 남은 작업
- 2b: 저장된 raw → 정규화 테이블(matches, teams, tournaments) 변환과 업서트. TBD 처리, KST 변환, 단계 slug 매핑.
- 2c: 팀 별칭(한글·영문), "오늘 경기 목록" CLI.

## 2b: 정규화 (구현됨)
`python cli.py normalize`는 `raw_responses`에서 엔드포인트·파라미터 조합별 최신 200 응답을 읽어 아래 테이블을 채운다. 재실행해도 결과가 같다(upsert, 테스트로 확인).

| 테이블 | 출처 | 비고 |
|---|---|---|
| tournaments | getTournamentsForLeague + getLeagues | league_slug는 getLeagues의 id→slug |
| stages | getStandings | slug가 단계 기준 키(play_ins/swiss/knockouts) |
| teams | getTeams | |
| matches | getStandings + getSchedule | 대회·단계는 standings, 시각·Bo·블록명은 schedule, 상태·승수는 schedule 우선 |
| match_teams | 위와 동일 | 팀 id는 standings, TBD는 `team_id = NULL` |
| match_links | getStandings `previousMatchIds` | 현재 샘플에서 항상 비어 있음 |

규칙:
- 팀 id: standings 우선, 없으면 (code, name)이 teams에서 유일할 때만 매칭, 아니면 NULL. 건수는 `report`의 `unresolved_team_slots`.
- 대회·단계: standings 조인으로만 확정. 조인 안 되는 경기는 NULL(`matches_without_tournament`).
- 시각은 UTC 문자열 그대로 저장한다. KST 변환은 표시 단계.

합의 대비 변경:
- raw 해시가 같으면 건너뛰는 최적화는 넣지 않았다. matches는 standings와 schedule을 합쳐서 만들기 때문에 한쪽만 건너뛰면 병합 결과가 틀어진다. 대신 항상 최신본 전체를 다시 병합하고 upsert한다. 데이터가 작아 비용이 낮다.

2b에서 새로 확인한 사실 (2026-10-15, 월즈 2026·2025 샘플):
- 월즈 2025 standings 41경기, 팀 칸 82개 모두 실제 팀 id가 채워졌고 전부 getTeams에 존재한다.
- `previousMatchIds`는 월즈 2026·2025 모두 전 경기에서 비어 있다(종료된 대회 포함). 대진 트리 복원에는 쓸 수 없다. 대안은 미정(규칙 파일의 포맷 정의 또는 블록 이름 기반).
- `rankings`는 종료된 2025 대회에서도 비어 있다. getStandings는 순위표 소스로 쓸 수 없다. 순위는 경기 결과로 직접 계산해야 한다.
- getStandings 경기에는 Bo 형식이 없다. `best_of`는 getSchedule에서만 온다. 일정에 안 잡힌 경기는 NULL(현재 7건).
- 존재하지 않는 id로 getStandings를 호출하면 200과 빈 `standings`가 온다(오류가 아님). 정규화는 이를 무시한다.

남은 것: 2c 팀 별칭, "오늘 경기 목록" CLI. 일정 과거 페이지(older 토큰) 수집은 아직 수집기에 없다.
