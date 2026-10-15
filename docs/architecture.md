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
