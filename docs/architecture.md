# 구조 설명

## 데이터 흐름
collectors(소스별 어댑터) → models(공통 스키마) → engine(계산) → notifier(후속 단계)

## 모듈
- `models/schema.py`: `Match`, `SeriesTeam`. 소스와 무관한 공통 형태. Standing, RosterEntry는 getStandings `rankings` 형식 확인 후 추가한다.
- `collectors/lolesports.py`: Riot lolesports API 어댑터. `parse_schedule_events`는 네트워크 없이 원본 응답 dict를 변환하므로 `data/raw_samples/`로 테스트한다. 보조 소스를 붙일 때 같은 `Match` 리스트를 반환하는 클래스를 추가한다.
- `engine/series.py`: 시리즈 상황 문구. 확정 승수는 `Bo // 2 + 1`, 남은 승수는 확정 승수에서 현재 승수를 뺀 값이다.
- `engine/swiss.py`: 스위스 팀 상태(진출/탈락 확정, 필요 승수, 결정전). 규칙 수치는 `rules/events/worlds_2026.json`에서 읽는다.
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

## 2c: 팀 별칭과 경기 목록 (구현됨)
- `rules/team_aliases.json`: 월즈 2026 출전 19팀의 한글명(`ko`), 약칭(`ko_short`), 영문명, 별칭. 키는 `team_id`(코드는 중복이라 쓰지 않음). 전부 `verified: false`이며 사용자 확인 전 값이다.
- `pipeline/aliases.py`: JSON → `team_aliases` 테이블 적재와 검증(미존재 team_id, 서로 다른 팀이 같은 별칭을 쓰는 경우), `resolve_alias`(공백·점·대소문자 무시, 유일할 때만 반환), `display_name`(한글 우선, 없으면 영문, TBD는 "미정").
- `pipeline/schedule_view.py`: KST 날짜 범위 조회와 한 줄 포맷. KST는 고정 오프셋 +9.
- `rules/events/worlds_2026.json`의 `entrants`: 직접 진출 15팀 + 플레이-인 4팀의 team_id.
- CLI: `python cli.py aliases`(적재·검증), `python cli.py today [--date YYYY-MM-DD] [--days N]`.

출전 팀 구성 (2026-10-15):
- 20팀이 아니라 19팀이다. 직접 진출 15팀 + 플레이-인 4팀. 플레이-인 통과 1팀이 스위스 16번째 자리를 차지한다.
- 플레이-인 4팀(C9, KC, FURIA, MVK)은 getStandings로 확인됨.
- 직접 진출 14팀은 Inven Global 팀 목록과 getTeams로 확인, LOS(CBLOL 1시드)는 추정. CBLOL 결승(LOS 대 FURIA) 결과를 찾지 못했고, FURIA가 플레이-인에 있으므로 LOS가 직접 진출로 추정했다.
- 스위스 시드 티어(LCS1/LCS2 등)는 팀 매칭을 하지 않았다. Team Liquid Alienware와 LYON이 LCS 직접 진출 두 팀이라는 것만 확인.

수정한 버그: 정식명과 약칭이 같은 팀(예: FURIA→푸리아)의 `ko_short` 행이 PK 중복으로 사라져 영문이 표시됐다. `display_name`이 두 종류를 우선순위로 조회하도록 바꾸고 테스트를 추가했다.

## 4a: 스위스 (구현됨)
화면을 두 종류로 나눈다.

| 명령 | 내용 |
|---|---|
| `python cli.py status <대회> --stage swiss` | 현재 진행 상태: 라운드별 일정·결과(시리즈 문구), 전적별 현황, 검증 경고 |
| `python cli.py scenario <대회> --stage swiss [--team 별칭]` | 경우의 수: 팀별 결정전 여부, 이기면/지면 결과, 다음 라운드 후보 상대, 도달 가능한 최종 전적(경로 수) |

`<대회>`는 대회 슬러그(예: `worlds_2026`, 과거 대회 `worlds_2025`). `--stage`를 생략하면 규칙 파일의 모든 단계를 순서대로 보여 준다.

구성:
- `engine/swiss.py`: DB와 무관한 계산. 라운드 배정(`assign_rounds`), 경기 재생(`replay`), 규칙 검증(`validate`), 최종 전적 경로 수(`final_paths`), 팀별 경우의 수(`team_scenarios`).
- `pipeline/swiss_data.py`: DB → `SwissMatch`. `pipeline/swiss_view.py`: 두 화면의 텍스트 출력.
- `rules/events/worlds_2026.json`의 `swiss`: 승/패 기준, 라운드별 경기 수 `[8,8,8,6,3]`, Bo 규칙.

판정 규칙:
- 진출은 3승, 탈락은 3패. 한쪽이 2승 또는 2패인 경기가 결정전(Bo3). 월즈 2025 33경기로 검증.
- 다음 라운드 후보 상대: 같은 전적이고 이미 만난 적 없는 팀. 같은 라운드에서 아직 끝나지 않은 팀은 어느 결과로든 그 전적이 될 수 있으면 포함. 현재 상대는 항상 제외.

가정과 한계:
- 라운드 배정은 (시작 시각, id) 순으로 정렬해 `round_sizes`만큼 자른다. 일정에 33경기가 모두 있어야 맞다. 월즈 2025에는 시각 정보가 없는 경기 2건이 있어 맨 앞(1라운드)으로 놓이며, 전적 기반 라운드와 일치하는지 `validate`가 검사한다.
- 후보 상대는 "될 수 있는 팀" 집합이다. 실제 매칭 알고리즘(시드 기준 등)은 미확인이라 상대를 확정하거나 확률을 매기지 않는다.
- 1라운드(추첨)는 후보를 계산하지 않는다. 대진 확정 전에는 일정만 보이고 경우의 수는 팀당 도달 가능한 최종 전적 경로 수만 나온다.
- 경로 수는 가능한 승패 순서의 개수이며 확률이 아니다.

검증(테스트):
- 월즈 2025 스위스 재생: 재대결 0, 두 팀 전적 일치, Bo 규칙 일치, 최종 전적 분포(3-0 2팀 · 3-1 3팀 · 3-2 3팀 진출).
- 라운드 2~5에서 실제 다음 상대가 후보 집합에 항상 포함, 라운드 진행 중 시점에서도 이기면/지면 결과별 실제 다음 상대가 포함.
- 수정한 버그: 진행 중 경기의 현재 상대가 "이기면" 후보에 들어가던 문제. 포함 관계 검사만으로는 잡히지 않아 별도 테스트를 추가했다.

## 4b: 토너먼트 (구현됨)
`python cli.py status <대회> --stage knockouts` / `python cli.py scenario <대회> --stage knockouts [--team 별칭]`. 스위스와 같이 진행 상태와 경우의 수를 분리했다.

원문 확인 (2026-10-16, 한글판·영문판 대조, https://lolesports.com/ko-KR/news/worlds-2026-primer):
- 8강 추첨: 스위스 3-0 두 팀이 3-2 팀을 상대로 무작위 배정. 나머지 4팀(남은 3-2 한 팀 + 3-1 세 팀)은 서로 무작위로 2경기. 월즈 2025 실제 8강과 일치.
- 토너먼트 같은 지역 제한은 원문에 없음(월즈 2025에서 HLE 대 GEN 성사). 제한 없음으로 처리.
- 4강·결승 대진 방식은 원문에 없음. 날짜만 안내됨. 토너먼트는 Bo5.
- 이전에 "요약이 서로 맞지 않는다"고 본 것은 3-2 팀이 세 팀이라는 점을 놓쳤기 때문이었다.

구성:
- `engine/knockout.py`: `build_rounds`(경기 id 순서로 8강4·4강2·결승1 분할), `feeders`(인접 두 경기의 승자가 다음 경기로), `validate_bracket`(이전 라운드 승자가 참가 팀에 있는지), `enumerate_outcomes`(남은 경기 결과를 모두 열거, 최대 2^7), `team_scenarios`, `qf_draw_options`(8강 추첨 가능 결과 18가지 열거).
- `engine/types.py`: 스위스와 토너먼트가 공유하는 `StageMatch`.
- `pipeline/knockout_view.py`: 두 화면. `rules/events/worlds_2026.json`의 `knockouts`: 구조, 추첨 규칙, 출처.

출력:
- `status`: 8강1~결승 일정·결과. 팀이 미정인 자리는 "8강1 승자"로 표시.
- `scenario` 추첨 전: 스위스 진출 8팀이 확정되면 가능한 추첨 결과 수와 팀별 8강 상대 후보(몇 가지 중). 8팀 전이면 안내만.
- `scenario` 추첨 후: 팀별 상태(우승/탈락 라운드/생존), 우승으로 이어지는 결과 조합 수(전체 중), 남은 라운드별 상대 확정 또는 후보.

가정과 한계:
- 대진 트리(어느 8강 승자끼리 4강에서 만나는지)는 월즈 2025 한 대회에서 확인한 추정이다. 이전 라운드 승자가 다음 경기 참가 팀에 없으면 `status`가 경고한다.
- 결과 조합 수는 경기 결과(승/패)의 개수이며 확률이 아니다. 팀 전력은 반영하지 않는다. Bo5 세트 스코어는 열거하지 않는다.
- 진행 중인 경기는 미결로 취급한다.
- 추첨 전 계산은 스위스 진출 8팀 구성이 3-0 2팀·3-2 3팀일 때만 한다. 같은 지역 제한이 없다는 가정이 틀리면 후보가 줄어든다.

검증(테스트): 월즈 2025 7경기를 시점별로 잘라(0~7경기 종료) 각 시점에서 결과 조합 수가 2^미결 경기 수와 같고, 실제 우승 팀이 항상 우승 가능, 실제 모든 대진이 상대 후보에 포함됨을 확인. 추첨 가능 결과 18가지에 실제 8강 대진이 포함됨.

## 4c: 플레이-인 (구현됨)
`python cli.py status <대회> --stage play_ins` / `python cli.py scenario <대회> --stage play_ins [--team 별칭]`.

구성:
- `engine/elimination.py`: 승자/패자 연결 그래프로 정의된 단판 탈락 대진의 범용 엔진. `order_roles`(시작 시각 순으로 역할 배정), `enumerate_outcomes`(남은 결과 전부 열거, 6경기면 최대 64가지), `team_scenarios`(팀별 진출 조합 수, 다음 경기와 상대, 패하면 탈락 여부, 라운드별 상대 후보), `validate`.
- `rules/events/worlds_2026.json`의 `play_in.structure`: `roles`(6개), `slots`(`W:역할`=승자, `L:역할`=패자, `seed`=1라운드 팀), `labels`, `advance_from`. 탈락 경기는 슬롯에서 `L:`로 참조되지 않는 경기로 계산해 도출한다(패자조 1경기, 패자조 결승, 결승).
- `pipeline/playin_view.py`: 두 화면. 팀이 미정인 자리는 "승자조 결승 승자"처럼 표시.

연결 구조 (경기 시각 순서): 1라운드 A, 1라운드 B → 승자조 결승(승자끼리), 패자조 1경기(패자끼리) → 패자조 결승(승자조 결승 패자 대 패자조 1경기 승자) → 결승(승자조 결승 승자 대 패자조 결승 승자). 결승 승자 1팀이 스위스 진출.

확인 상태:
- 확인됨: 1라운드 종료 후 승자조 결승과 패자조 1경기에 예상한 팀이 채워졌다(실데이터, 스냅샷 `tests/fixtures/play_in_20261016.json`).
- 추정: 패자조 결승과 결승의 연결. 앞 경기가 끝나 팀이 채워지면 `status`의 검증 경고로 확인된다.
- 미확인: 결승 재경기(브래킷 리셋). 경기가 6개뿐이라 없는 것으로 보이나 규정 문서로 확인하지 못했다.

검증(테스트):
- 과거 사례가 없어 6경기의 64가지 결과 전부를 시뮬레이션하고, 각 결과마다 0~6경기 종료 시점으로 잘라 결과 조합 수가 2^미결 경기 수와 같음, 진출 조합 합이 전체와 같음, 실제 진출 팀이 항상 진출 가능, 종료 시 진출 1팀·탈락 3팀임을 확인.
- 경기 id가 시간 순서와 다르게 배치돼도 연결이 맞음(실데이터의 id 특성을 재현).
- 실데이터 스냅샷에서 진출 조합 KC 6/16, MVK 6/16, C9 2/16, FUR 2/16 (손으로 검산한 값과 일치).

한계: 결과 조합 수는 경기 결과(승/패)의 개수이며 확률이 아니다. Bo5 세트 스코어는 열거하지 않는다. 진행 중인 경기는 미결로 취급한다.


## 규칙 구조: 대회별 파일 (연도별 갱신)
규칙은 해마다 달라질 수 있어 대회 슬러그마다 파일 하나를 둔다. 실행 중에 AI가 규칙 문서를 읽거나 해석하지 않는다. 규칙 파일은 사람이 공식 문서를 읽고 입력한 파라미터이고, 판정은 코드와 테스트가 한다.

- 위치: `rules/events/<대회 슬러그>.json`. 슬러그는 API의 대회 `slug`(예: `worlds_2026`)와 같다. 파일 이름과 `event` 값이 다르면 로드가 실패한다.
- 최상위 키: `schema_version`, `event`, `league_slug`, `verified_at`, `sources`, `stages`, `entrants`(선택), `notes`(선택). 이 밖의 키는 거부된다. 설명은 `notes`에만 쓴다.
- `stages[]`: `slug`(API의 단계 슬러그), `type`, `label`, `params`, `notes`(선택).
- 형식 종류(`type`)와 `params` (`engine/rules.py`에 닫힌 목록으로 정의, 목록 밖 키는 거부):

| type | 엔진 | params |
|---|---|---|
| `swiss` | `engine/swiss.py` | `win_target`, `loss_limit`, `round_sizes`, `best_of{normal, decisive}` |
| `single_elim` | `engine/knockout.py` | `round_sizes`, `round_labels`, `wiring`(`adjacent_pairs`), `draw`(`none`/`worlds_swiss_records`, 선택) |
| `bracket_graph` | `engine/elimination.py` | `roles`, `labels`, `slots`, `advance_from`, `order`(`start_time`) |

- 값이 코드에 연결된 항목: `wiring`, `draw`, `order`는 허용 값이 코드에 고정돼 있다. 새 값을 쓰려면 엔진에 구현을 추가해야 하며, 그 전에는 로드 단계에서 실패한다.
- 검증: `python cli.py rules`가 모든 대회 규칙 파일을 검사한다. 테스트(`tests/test_rules.py`)가 잘못된 규칙 19종이 거부되는지, 모든 `params` 키를 코드가 읽는지(죽은 키 없음)를 확인한다.
- 등록: `pipeline/registry.py`가 형식 종류별 화면을 연결한다. 새 형식 종류는 엔진, 화면, `STAGE_TYPES`, 등록부를 함께 추가해야 하고, 테스트가 이 둘의 불일치를 잡는다.
- 팀 별칭(`rules/team_aliases.json`)은 team_id 기준 전역 파일로 해마다 누적한다. 대회별 출전 팀은 규칙 파일의 `entrants`에 둔다.
- 과거 대회 규칙 파일(`worlds_2025`)은 삭제하지 않고 회귀 검증에 쓴다. 월즈 2025는 플레이-인 단계의 형식을 확인하지 못해 단계를 넣지 않았다.

## 공개 수준 정책 (구현됨)
`python cli.py show <대회>`는 정책에 따라 지금 보여 줄 것만 보여 준다. `status`(진행 상태)와 `scenario`(경우의 수)는 정책과 무관하게 항상 직접 볼 수 있다.

수준: 1 일정·결과, 2 대진·진출 경우의 수, 3 우승 경우의 수.

- 정책 파일: `rules/display_policy.json`. 단계 형식(`swiss`, `bracket_graph`, `single_elim`)별 `base`(기본 수준)와 `promote`(승격 규칙 `{when, to}`). 외부 규정이 아니라 앱의 설계 결정이라 해마다 수집하지 않는다.
- 대회별 덮어쓰기: 대회 규칙 파일의 `display_policy.stages.<단계 슬러그>`. 같은 형식으로 검증되고, 있으면 기본값보다 우선한다.
- 조건은 `engine/visibility.py`의 닫힌 목록만 쓸 수 있다. 목록 밖 이름, 해당 형식에서 쓸 수 없는 조건, 형식의 최대 수준(`swiss`/`bracket_graph` 2, `single_elim` 3)을 넘는 값은 로드 시점에 거부된다.

| 조건 | 범위 | 의미 |
|---|---|---|
| `followed_team_in_match` | 경기 | 팔로우한 팀이 있는 경기 |
| `decisive_match` | 경기 | 이기면 진출 또는 지면 탈락이 걸린 경기 (스위스: 2승/2패 팀 포함, 플레이-인: 탈락 경기와 결승, 토너먼트: 전 경기) |
| `last_round_match` | 경기 | 단계의 마지막 라운드(스위스 5라운드, 결승 등) |
| `followed_team_in_stage` | 단계 | 팔로우한 팀이 있는 단계 |
| `pre_draw_ready` | 단계 | 앞 단계(스위스)가 끝나 진출 8팀이 확정되고 추첨 전 |
| `draw_done` | 단계 | 첫 라운드 대진이 모두 확정 |

현재 기본값:
- 스위스: 기본 1. 팔로우 팀 경기, 결정전, 마지막 라운드 경기는 해당 경기에 한해 2로 승격되어 그 경기 팀들의 경우의 수만 추가로 보여 준다.
- 플레이-인: 기본 2.
- 토너먼트: 기본 1, 추첨 대기에 2, 추첨 후 3.

구성: `pipeline/visibility_data.py`(DB에서 평가용 문맥을 만든다), `engine/visibility.py`(순수 평가), `pipeline/show.py`(화면 조합).

검증: 월즈 2025 스위스 3라운드를 대진 확정·미진행으로 가정해 결정전 4경기와 팔로우 팀 1경기가 정확히 승격됨을 확인. 월즈 2026 스위스 일정의 Bo 분포가 결정전 규칙에서 유도한 값과 일치(라운드별 Bo1/Bo3: 8·0, 8·0, 4·4, 0·6, 0·3).

한계:
- 팀이 정해지지 않은 경기는 `followed_team_in_match`, `decisive_match`가 거짓/미정이라 승격되지 않는다. 마지막 라운드만 팀과 무관하게 판정된다.
- 승격 대상은 미완료 경기다. 종료된 경기는 승격 평가에서 제외한다.
- 사용자별 덮어쓰기 설정(단계별 항상 보기/숨기기)은 만들지 않았다. 앱 단계에서 사용자 설정으로 추가한다.
