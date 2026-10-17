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

## 라이브 확인 (2026-10-16 KST 10시경, 플레이-인 진행 중)
샘플: `data/raw_samples/getLive_inProgress.json`
- 확인됨: 진행 중 경기의 `state`는 `inProgress`. 경기 종료 후 `completed`.
- 확인됨: getLive는 getSchedule과 같은 이벤트 구조에 `tournament.id`, `streams`, 세트별 `match.games[]`(`number`, `state`, `teams[].side`, `vods`)가 추가된다. 세트 `state`는 `completed`/`inProgress`/`unstarted`. 현재 몇 세트가 진행 중인지는 `games[].state`로 알 수 있다.
- 확인됨: 세트가 끝날 때마다 `result.gameWins`가 갱신된다(MVK 2 : FURIA 0, 3세트 진행 중 시점).
- 확인됨: 팀 `record`(시즌 전적)는 시리즈 종료 시 갱신된다(KC 1-0, C9 0-1 / 종료 직후).
- 확인됨: 라이브 중인 경기가 없으면 `events: []`.
- 미확인: 폴링 간격에 따른 갱신 지연, 세트 사이 휴식 시간의 `state`, 경기 종료 후 getLive에서 사라지는 시점.

## 플레이-인 구조 확인 (2026-10-16, 월즈 2026 진행 중)
- 확인됨: getStandings `play_ins`에 6경기가 대회 시작 시점부터 있었다. 전부 Bo5.
- 확인됨: R1(KST 10/16) 종료 후 id 171790에 KC 대 MVK(R1 승자끼리), id 171794에 C9 대 FUR(R1 패자끼리)가 채워졌다. 더블 엘리미네이션의 승자조 경기와 패자조 경기에 해당.
- 추정: id 171798(KST 10/18)은 승자조 경기 패자 대 패자조 경기 승자, 마지막 경기(KST 10/19)는 승자조 승자 대 패자조 결승 승자. 앞 두 경기가 끝나 팀이 채워지면 확인한다.
- 미확인: 결승 재경기(브래킷 리셋) 여부. 경기는 6개뿐이라 없는 것으로 보이나 규정 문서로 확인하지 못했다.
- 주의: 경기 id 순서가 시간순이 아니다. R1 두 경기는 id와 시각이 역순이고 결승 id만 훨씬 크다. 토너먼트처럼 id 순서로 연결을 복원하면 안 되고 팀이 채워지는 방식으로 확인해야 한다.
- 과거 대회 검증 불가: 월즈 2025 `play_ins`에는 1경기만 있고(T1 대 IG, 시각 없음) 월즈 2024 standings는 비어 있다. 이번 형식(4팀 Bo5 더블 엘리미네이션)의 과거 사례는 이 엔드포인트에서 얻지 못했다.

## 국제대회 목록과 LCK 일정 구조 (2026-10-17 확인)
- 확인됨: getLeagues의 지역 "국제 대회" 리그는 worlds, msi, first_stand, asian_games, demacia_cup(DCGI), wsci, ewc_lol, tft_esports, wqs. 2026 대회가 있는 것: first_stand(03-16~03-23), msi(06-27~07-12), ewc_lol(07-14~07-19), wsci(09-19~10-02), asian_games(09-27~10-02), demacia_cup(10-02~10-17), worlds(10-15~11-15). tft_esports, wqs는 2026 대회 없음. DCGI, WSCI가 LCK와 어떤 관계인지는 미확인.
- 확인됨: LCK 2026 대회 3개와 기간: lck_split_1_2026(01-13~03-01, 컵), lck_split_2_2026(03-31~06-14, 정규 리그 90경기 + MSI로 가는 길 5경기), lck_split_3_2026(07-28~09-13, 레전드/라이즈 그룹 각 20경기 + 플레이-인 3경기 + 지역별 챔피언십 10경기).
- 확인됨: LCK 일정의 `blockName`은 "N주 차"(1~13주 차), "플레이-인", "플레이오프", "결승", "토너먼트 스테이지"이고 라운드(1~4라운드) 정보는 없다. 같은 이름("1주 차" 등)이 대회마다 반복되므로 대회 구분 없이 쓰면 안 된다.
- 확인됨: LCK getStandings의 `rankings`는 채워져 있다(월즈와 다름): `{ordinal, teams[{record}]}`. 정규 리그 10팀, 그룹 각 5팀.
- 시기 관계(확인됨): 정규 리그(스플릿 2) 종료 06-14는 MSI 시작 06-27보다 앞, 스플릿 3(07-28~09-13)은 MSI 종료 07-12보다 뒤. 월즈(10-15)는 스플릿 3 이후.
- 미확인: 어떤 LCK 단계가 어떤 국제대회 출전권을 결정하는지(MSI, First Stand, 월즈, EWC, 아시안게임), 레전드/라이즈 그룹 배정 기준, 순위 동률 처리.
- 주의: 2026 LCK는 소스 기준 4라운드(1~2라운드 + 3~4라운드)이고, 5라운드 구조는 2025 방식으로 보인다(추정). 라운드 수는 해마다 다를 수 있다.

## LCK 순위 규칙 검증 (2026-10-17)
공식 포맷 설명(https://lolesports.com/ko-kr/news/2026-lck-format-explainer)에는 순위 산정 기준, 동률 처리, 그룹 분할 규칙이 없다. 아래는 API의 `rankings`(순서)와 경기 결과를 대조해 추정한 것이다. 검증 데이터: `tests/fixtures/lck_ranked_sections.json`(순위 구간 18개, 2021~2026).

- 확인됨: 2026 정규 리그는 10팀 더블 라운드 로빈 90경기(쌍마다 정확히 2회). 라운드는 API에 없고, 같은 두 팀의 첫 만남을 1라운드, 두 번째를 2라운드로 계산하면 1라운드 45경기가 전부 끝난 뒤 2라운드가 시작된다(1라운드 마지막 05-01 08:00Z, 2라운드 첫 경기 10:00Z). 스플릿 3 그룹(5팀 더블 라운드 로빈)도 같은 방식으로 3·4라운드(각 20경기)로 나뉜다.
- 추정(26개 동률 쌍 중 25개 일치, 1개는 세트 득실도 동률): 순위 = ① 시리즈 승수(패수) ② 전체 세트 득실 ③ 직접 대결 시리즈 ④ 순위 결정전. 대안은 틀렸다: 직접 대결을 먼저 보면 14개 구간 중 10개만 일치, 세트 득실만 12개, 직접 대결만 5개, 세트 승률은 동률 쌍 1건이 반대.
- 추정(사례 3건): 세트 득실까지 같을 때 직접 대결로 가른다. 2021 서머 GEN 대 NS(2-0), 2026 레전드 그룹 GEN 대 HLE(누적 3-1), 라이즈 그룹 NS 대 BFX(누적 3-1).
- 확인됨: 순위 결정전이 있는 해가 있다(2025 스플릿 2의 DK 대 KT, 2022 스프링의 BRO 대 DNS). 이 경기는 API의 전적(`record`)에는 포함되지만 순서는 결정전 이전 전적으로 정해지고, 결정전은 마지막 동률에서만 쓰인다. 쌍이 정규 라운드 수를 넘어 만난 경기를 결정전으로 분리한다.
- 확인됨: 2026 스플릿 3 그룹의 순위(`ordinal`)는 정규 리그(1~2라운드) 전적을 합산한 누적 전적으로 정해진다. `record` 필드는 그룹 경기만의 전적이라 순서와 어긋나 보인다(레전드 그룹에서 DK 6-2가 T1 3-5보다 아래). 누적 승수와 누적 세트 득실로 두 그룹 모두 순서가 재현된다.
- 확인됨(2026 한 해): 레전드 그룹은 정규 리그 1~5위, 라이즈 그룹은 6~10위.
- 알려진 차이: 2025 스플릿 3 레전드 그룹은 제 규칙과 한 쌍이 다르다(T1과 HLE가 20-10 동률, API는 T1이 위인데 누적 세트 득실은 HLE가 앞서고 그룹 안만 보면 T1이 앞섬). 규칙이 해마다 달랐다는 증거로 보고, 올해(2026) 방식을 기준으로 둔다. 2025 라이즈 그룹은 일치.
- 미확인: 이 추정 규칙이 공식 규정과 같은지, 순위 결정전을 치르는 조건, 컷라인(플레이오프·국제대회 출전권)과 순위의 연결.
