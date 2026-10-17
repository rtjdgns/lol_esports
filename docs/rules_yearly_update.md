# 해마다 규칙을 새로 입력하는 절차

규칙은 사람이 공식 문서를 읽고 파일로 옮긴다. 코드가 문서를 읽거나 해석하지 않는다.

1. 공식 규정집·프라이머를 찾는다 (예: https://lolesports.com 의 해당 대회 프라이머). 출처 URL과 확인한 날짜를 남긴다.
2. 직전 대회 파일을 복사해 새 파일을 만든다: `rules/events/<대회 슬러그>.json`. `event`는 파일 이름과 같게, 슬러그는 `getTournamentsForLeague`의 `slug`.
3. `stages`를 대회 구성에 맞게 고친다. 각 단계의 `slug`는 `getStandings`의 `stages[].slug`와 같아야 한다.
4. 형식이 이전과 같은 종류면 `params` 수치만 고친다. 새 종류의 형식이면 새 엔진이 필요하므로 먼저 구조를 제안하고 합의한 뒤 구현한다.
5. 확인하지 못한 부분은 `notes`에 "미확인"으로 적는다. 추정은 "추정"이라고 적는다.
6. `python cli.py rules`로 검증한다.
7. 출전 팀은 `entrants`에 team_id로 넣고, 한글 표기는 `rules/team_aliases.json`에 추가한 뒤 `python cli.py aliases`로 검증한다.
8. 대회가 진행되면 `python cli.py status <대회>`의 검증 경고를 확인한다. 경고는 규칙과 실제 데이터가 어긋났다는 뜻이다.
9. 대회가 끝나면 응답 샘플과 테스트를 남겨 다음 해 회귀 검증에 쓴다.

공개 수준 정책(`rules/display_policy.json`)은 외부 규정이 아니라 앱의 설계 결정이므로 해마다 수집하지 않는다. 대회에서 정책을 다르게 하고 싶을 때만 대회 규칙 파일에 `display_policy.stages.<단계>` 를 넣는다.
