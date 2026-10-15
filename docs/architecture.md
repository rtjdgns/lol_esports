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
