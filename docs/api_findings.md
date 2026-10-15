# Riot lolesports API 검증 결과

검증일: 2026-10-15. 방법: `scripts/verify_riot_api.py` 실제 호출. 원본 응답은 `data/raw_samples/`.
기준 URL: `https://esports-api.lolesports.com/persisted/gw/` (비공식, 문서 없음).

## 확인됨 (실제 응답으로 확인)

- 인증: `x-api-key` 헤더 없으면 403, 있으면 200. 키는 커뮤니티에 공유된 공개 값을 사용했다. 키 배포 주체와 이용 조건은 확인하지 못했다.
- 동작하는 엔드포인트: getLeagues, getTournamentsForLeague, getSchedule, getStandings, getLive, getEventDetails, getTeams, getCompletedEvents (모두 200).
- `hl=ko-KR` 적용됨. 리그명·단계명이 한국어로 반환된다 (예: "월드 챔피언십", "스위스", "플레이-인", "8강").
- getSchedule: 이벤트별 `state`(`completed`/`unstarted` 확인), `blockName`(단계/라운드 이름), `match.strategy`(`type: bestOf`, `count`), `match.teams[].result.gameWins`, `match.teams[].result.outcome`, `match.teams[].record`(wins/losses)가 존재한다. 시리즈 스코어, Bo 형식, 진행 상태는 이 엔드포인트만으로 얻을 수 있다.
- getSchedule 페이징: `pages.older` / `pages.newer` 토큰. 응답 한 번에 약 80건이며 과거 완료분과 미래 예정분이 섞여 있다.
- getTournamentsForLeague: `id`, `slug`(예: `worlds_2026`), `startDate`, `endDate`. 월즈 2026은 2026-10-15 ~ 2026-11-15로 응답됨 (리그 공식 일정과의 대조는 안 함).
- getStandings: `stages[]` → `{id, name, slug, type, sections[]}`. 월즈 2026은 `play_ins`, `swiss`, `knockouts` 세 단계. 각 section은 `matches[]`(id, state, previousMatchIds, teams)와 `rankings[]`를 갖는다.
- getEventDetails: `match.games[]`에 게임 번호, 상태, 진영(blue/red), VOD 정보.
- getTeams: 1586팀 반환, 그중 963팀에 `players[]`(role, summonerName, firstName, lastName). `status`(예: archived)와 `homeLeague` 필드가 있다.
- 응답에 rate limit 관련 헤더(Retry-After, X-RateLimit-*)는 없었다.

## 추정

- (정정) `previousMatchIds`는 월즈 2026·2025 전 경기에서 비어 있어 대진 트리 복원에 쓸 수 없다. 확인됨(2026-10-15).
- (정정) getStandings의 `rankings`는 종료된 월즈 2025에서도 빈 배열이다. 순위표 소스로 쓸 수 없다. 확인됨(2026-10-15).
- getStandings가 규칙 엔진 입력(타이브레이커 포함)에는 부족할 가능성이 높다. 타이브레이커 정보 필드를 보지 못했다.

## 미확인

- getLive 응답 구조: 현재 생중계가 없어 `events: []`만 받았다. 경기 중 호출해 다시 확인해야 한다.
- 진행 중 상태 값(`inProgress` 등)과 경기 중 `gameWins` 갱신 지연.
- getCompletedEvents: `tournamentId`를 넘겼는데도 `events: []`였다. 필수 파라미터가 다를 수 있다. 확인 필요.
- 호출 제한: 헤더로는 알 수 없다. 반복 호출 테스트를 하지 않았다.
- 선발 라인업(경기 전) 제공 여부. getEventDetails의 경기 전 응답을 보지 못했다.
- 이용 약관: Riot 개발자 정책상 이 API의 앱 사용이 허용되는지 확인하지 못했다. 사전조사 프롬프트 A-6 대상.
- 키가 바뀌거나 막힐 위험. 어댑터 구조로 대비한다.

## 설계 반영

- 시리즈 상황 문구(`2 : 1, 1승 남음`)는 getSchedule 필드(`strategy.count`, `gameWins`)만으로 계산 가능하다. 1단계에서 바로 구현한다.
- 순위 경우의 수는 getStandings가 아니라 getSchedule의 경기 목록 + `rules/` 규칙 파일을 입력으로 쓰는 쪽이 안전하다. `rankings` 형식이 확정되기 전에는 이를 의존하지 않는다.
- 월즈 2026은 오늘 개막이므로 실시간 검증 대상이 된다. 스위스 단계가 경우의 수 계산의 첫 대상이다. 스위스 진출/탈락 규칙은 공식 규정집에서 확인해 규칙 파일로 옮겨야 한다 (미확인).
- 모바일 우선이므로 알림은 웹 푸시/FCM/텔레그램 중 선택이 필요하다. 사전조사 E 항목에서 결정한다.

## 재현

```
pip install -r requirements.txt
export LOLESPORTS_API_KEY=<키>
python scripts/verify_riot_api.py
python scripts/verify_riot_api.py --no-key
```

## 월즈 2026 규칙 확인 (2026-10-15)

출처: https://lolesports.com/ko-KR/news/worlds-2026-primer (1차 출처, WebFetch 요약 기준이라 원문 대조 필요)

- 확인됨: 플레이-인 4팀 Bo5 더블 엘리미네이션(10/16~19), 스위스 16팀 5라운드(10/24~11/1), 3승 진출·3패 탈락, 토너먼트 8팀 Bo5.
- 미확인: 스위스 결정전의 Bo3 여부(프라이머가 "단판승제, 3판 2선승제"를 병기), 타이브레이커 규칙(언급 없음).
- 규칙 파일: `rules/worlds_2026.json`
