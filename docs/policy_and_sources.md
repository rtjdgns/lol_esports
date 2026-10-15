# 정책 및 보조 소스 조사

조사일: 2026-10-15. 검색 요약 + 페이지 조회 기준이며 원문 전체를 읽은 것은 아니다. 법적 판단이 아니다.

## A. Riot lolesports API

| 항목 | 결론 | 근거 | 확실성 |
|---|---|---|---|
| 인증 | `x-api-key` 헤더 필요. 없으면 403 | 직접 호출 (2026-10-15) | 확인됨 |
| 키 획득 | 신청 절차 없음. 비공식 문서에 공개 값이 게재돼 있고 그 값으로 200 확인 | [vickz84259 비공식 문서](https://vickz84259.github.io/lolesports-api-docs/) | 확인됨 (키 출처가 Riot 공식인지는 미확인) |
| 공식 지위 | 비공식·무문서. 문서 자체가 "Unofficial", 버전 `1.0.0-alpha-1` | 같은 문서 | 확인됨 |
| 안정성 | 언제든 바뀌거나 중단될 수 있다고 CLI 프로젝트가 명시. 키 차단 사례는 검색에서 못 찾음 | [Apify 스크레이퍼](https://apify.com/jungle_synthesizer/lol-esports-worlds-2026-schedule-results-scraper), [lolesports-api(PyPI)](https://pypi.org/project/lolesports-api/) | 추정 |
| 호출 제한 | 문서에 없음. 60회 연속 호출(2.8초) 전부 200, 제한 헤더 없음 | 직접 호출 | 확인됨(이 규모에서만). 상한은 미확인 |
| 이용 약관 | Riot 개발자 정책은 이 API·e스포츠 데이터를 직접 언급하지 않음. "supported services를 데이터 수집에 쓰라"는 문장이 있고, 제품은 개발자 포털 등록·감사가 필요하며 법적 고지 문구 게시가 필요 | [Riot 개발자 정책](https://developer.riotgames.com/policies/general) | 확인됨(정책 문구). 이 API에 대한 허용 여부는 미확인 |
| 추가 엔드포인트 | `getGames`, `getWindow`, `getDetails`(feed.lolesports.com livestats) 존재 | 비공식 문서 | 확인됨(문서상), 호출 검증은 안 함 |
| 호스트 | `esports-api.lolesports.com`, 대체 `prod-relapi.ewp.gg` | 비공식 문서 | 문서상 |

해석(추정): 개인·비영리 소규모 사용은 현실적으로 동작하지만 정책상 보증이 없다. 공개 배포하거나 수익화할 경우 개발자 포털 등록과 Riot의 판단이 필요하다. 포트폴리오로 공개할 때는 "Riot 비후원" 고지 문구를 넣고, 키를 앱 바이너리에 넣지 않는다(정책의 키 취급 문구).

## 이전 검증의 정정
- getCompletedEvents가 빈 응답이었던 이유: 대상 `tournamentId`가 월즈 2026이고 오늘 개막이라 완료 경기가 없었을 가능성이 높다 (추정). 파라미터 형식은 문서상 `tournamentId` 배열이라 문제가 없어 보인다. 과거 대회 id로 재호출해 확인 필요.
- getSchedule 페이징: `pages.older` 토큰으로 가져온 페이지는 2023-10 ~ 2025-10 구간 80건이었다. 한 리그의 과거를 토큰으로 거슬러 올라가는 방식이며 대회 단위로 잘리지 않는다. 대회별 필터는 수집 후 처리해야 한다.

## B. 보조 소스

| 소스 | 결론 | 근거 | 확실성 |
|---|---|---|---|
| PandaScore 무료 | 시간당 1000회. 일정 및 사전 데이터 제공 | [요금](https://pandascore.co/pricing), [호출 제한 문서](https://developers.pandascore.co/docs/rate-and-connections-limits) | 확인됨 |
| PandaScore 무료의 한계 | 경기 후 데이터, 실시간 미포함. 시리즈 스코어 제공 여부와 LoL 포함 여부는 페이지에서 확인 못함. 상업 이용 조건 미기재 | 같은 페이지 | 미확인 |
| PandaScore 유료 | 게임당 월 €400부터 | 같은 페이지 | 확인됨 |
| Leaguepedia(Cargo) | 접근 문서·호출 제한·라이선스 페이지를 조회하지 못함(HTTP 402). 커뮤니티 클라이언트(poro)가 Cargo 쿼리를 쓰고 있음 | [poro](https://github.com/pacexy/poro) | 미확인 |
| Oracle's Elixir | 검색 실패(동명의 Oracle 사 결과만 나옴). 이용 조건 미확인 | - | 미확인 |

## 결정
- 주 소스: Riot lolesports API 유지. 대체 가능성을 위해 어댑터 구조 유지.
- 보조 소스 전환 조건: 키 차단, 필드 제거, 정책 문제 확정 중 하나.
- 보조 후보 우선순위(추정): PandaScore 무료는 실시간 미포함이라 알림 용도에 부적합. 로스터·이적은 Leaguepedia가 후보지만 접근 조건 확인이 먼저다.

## 직접 해봐야 할 것
1. Riot 개발자 포털(https://developer.riotgames.com)에서 이용 약관 전문과 e스포츠 데이터 관련 문의 경로 확인. 공개 배포 전 필수.
2. PandaScore 계정을 만들어 무료 키로 LoL 경기 응답에 시리즈 스코어가 있는지 호출로 확인.
3. Leaguepedia 도움말 페이지를 브라우저로 열어 Cargo 접근 방식, 호출 제한, 라이선스 확인.
4. Oracle's Elixir 사이트의 데이터 이용 조건 확인.
