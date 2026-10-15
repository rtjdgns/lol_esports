# 수집 필드 목록

`scripts/inventory_fields.py`가 `data/raw_samples/` 원본에서 생성. 채움률 = null/빈 값이 아닌 비율.

## getCompletedEvents

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|

## getEventDetails

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|
| `data.event.id` | str | 1/1 | 113475798006599034 |
| `data.event.league.id` | str | 1/1 | 98767975604431411 |
| `data.event.league.image` | str | 1/1 | http://static.lolesports.com/leagues/159 |
| `data.event.league.name` | str | 1/1 | 월드 챔피언십 |
| `data.event.league.slug` | str | 1/1 | worlds |
| `data.event.match.games[].id` | str | 1/1 | 113475798006599035 |
| `data.event.match.games[].number` | int | 1/1 | 1 |
| `data.event.match.games[].state` | str | 1/1 | completed |
| `data.event.match.games[].teams[].id` | str | 2/2 | 99566408219409348 ; 113661839307879869 |
| `data.event.match.games[].teams[].side` | str | 2/2 | blue ; red |
| `data.event.match.games[].vods[].endMillis` | NoneType,int | 9/17 | 5907000 ; 5706000 |
| `data.event.match.games[].vods[].firstFrameTime` | str | 17/17 | 2025-10-15T04:33:07.268Z ; 2025-10-15T04:36:16.144Z |
| `data.event.match.games[].vods[].id` | str | 17/17 | 115382480184187384 ; 115378587900911914 |
| `data.event.match.games[].vods[].locale` | str | 17/17 | cs-CZ ; de-DE |
| `data.event.match.games[].vods[].mediaLocale.englishName` | str | 17/17 | Czech (Czechia) ; German (Germany) |
| `data.event.match.games[].vods[].mediaLocale.locale` | str | 17/17 | cs-CZ ; de-DE |
| `data.event.match.games[].vods[].mediaLocale.translatedName` | str | 17/17 | Čeština ; Deutsch |
| `data.event.match.games[].vods[].offset` | int | 17/17 | 0 |
| `data.event.match.games[].vods[].parameter` | str | 17/17 | 2592249086 ; 2592250623 |
| `data.event.match.games[].vods[].provider` | str | 17/17 | twitch ; youtube |
| `data.event.match.games[].vods[].startMillis` | NoneType,int | 9/17 | 2234000 ; 2033000 |
| `data.event.match.strategy.count` | int | 1/1 | 1 |
| `data.event.match.teams[].code` | str | 2/2 | VKS ; TSW |
| `data.event.match.teams[].id` | str | 2/2 | 99566408219409348 ; 113661839307879869 |
| `data.event.match.teams[].image` | str | 2/2 | http://static.lolesports.com/teams/16705 ; http://static.lolesports.com/teams/17745 |
| `data.event.match.teams[].name` | str | 2/2 | Vivo Keyd Stars ; Team Secret Whales |
| `data.event.match.teams[].result.gameWins` | int | 2/2 | 0 ; 1 |
| `data.event.tournament.id` | str | 1/1 | 113475452383887518 |
| `data.event.type` | str | 1/1 | match |

## getLeagues

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|
| `data.leagues[].displayPriority.position` | int | 51/51 | 0 ; 1 |
| `data.leagues[].displayPriority.status` | str | 51/51 | force_selected ; selected |
| `data.leagues[].id` | str | 51/51 | 98767975604431411 ; 98767991325878492 |
| `data.leagues[].image` | str | 51/51 | http://static.lolesports.com/leagues/159 ; http://static.lolesports.com/leagues/159 |
| `data.leagues[].name` | str | 51/51 | 월드 챔피언십 ; MSI |
| `data.leagues[].priority` | int | 51/51 | 1 |
| `data.leagues[].region` | str | 51/51 | 국제 대회 ; 한국 |
| `data.leagues[].slug` | str | 51/51 | worlds ; msi |

## getLive

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|

## getSchedule

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|
| `data.schedule.events[].blockName` | str | 80/80 | 스위스 ; 8강 |
| `data.schedule.events[].league.name` | str | 80/80 | 월드 챔피언십 |
| `data.schedule.events[].league.slug` | str | 80/80 | worlds |
| `data.schedule.events[].match.flags[]` | str | 43/43 | hasVod ; isSpoiler |
| `data.schedule.events[].match.id` | str | 80/80 | 113475798006599034 ; 113475798006664572 |
| `data.schedule.events[].match.strategy.count` | int | 80/80 | 1 ; 3 |
| `data.schedule.events[].match.strategy.type` | str | 80/80 | bestOf |
| `data.schedule.events[].match.teams[].code` | str | 160/160 | VKS ; TSW |
| `data.schedule.events[].match.teams[].image` | str | 160/160 | http://static.lolesports.com/teams/16705 ; http://static.lolesports.com/teams/17745 |
| `data.schedule.events[].match.teams[].name` | str | 160/160 | Vivo Keyd Stars ; Team Secret Whales |
| `data.schedule.events[].match.teams[].record` | NoneType | 0/76 |  |
| `data.schedule.events[].match.teams[].record.losses` | int | 84/84 | 3 ; 2 |
| `data.schedule.events[].match.teams[].record.wins` | int | 84/84 | 1 ; 0 |
| `data.schedule.events[].match.teams[].result` | NoneType | 0/76 |  |
| `data.schedule.events[].match.teams[].result.gameWins` | int | 84/84 | 0 ; 1 |
| `data.schedule.events[].match.teams[].result.outcome` | NoneType,str | 80/84 | loss ; win |
| `data.schedule.events[].startTime` | str | 80/80 | 2025-10-15T05:00:00Z ; 2025-10-15T06:00:00Z |
| `data.schedule.events[].state` | str | 80/80 | completed ; unstarted |
| `data.schedule.events[].type` | str | 80/80 | match |
| `data.schedule.pages.newer` | str | 1/1 | bmV3ZXI6OjExNTY2MDU0MDcyNjA5NTA5Nw== |
| `data.schedule.pages.older` | str | 1/1 | b2xkZXI6OjExMzQ3NTc5ODAwNjU5OTAzNA== |

## getStandings_115660540725177488

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|
| `data.standings[].stages[].id` | str | 3/3 | 115660540725570705 ; 115660540725570706 |
| `data.standings[].stages[].name` | str | 3/3 | 플레이-인 ; 스위스 |
| `data.standings[].stages[].sections[].matches[].id` | str | 46/46 | 115660588583040710 ; 115660588583171786 |
| `data.standings[].stages[].sections[].matches[].state` | str | 46/46 | unstarted |
| `data.standings[].stages[].sections[].matches[].teams[].code` | str | 92/92 | FUR ; MVK |
| `data.standings[].stages[].sections[].matches[].teams[].id` | str | 92/92 | 100205576309502431 ; 107251245690956393 |
| `data.standings[].stages[].sections[].matches[].teams[].image` | str | 92/92 | http://static.lolesports.com/teams/FURIA ; http://static.lolesports.com/teams/17670 |
| `data.standings[].stages[].sections[].matches[].teams[].name` | str | 92/92 | FURIA ; MVK Esports |
| `data.standings[].stages[].sections[].matches[].teams[].result` | NoneType | 0/88 |  |
| `data.standings[].stages[].sections[].matches[].teams[].result.gameWins` | int | 4/4 | 0 |
| `data.standings[].stages[].sections[].matches[].teams[].result.outcome` | NoneType | 0/4 |  |
| `data.standings[].stages[].sections[].matches[].teams[].slug` | str | 92/92 | furia ; saigon-buffalo-esports |
| `data.standings[].stages[].sections[].name` | str | 3/3 | 플레이-인 ; 스위스 |
| `data.standings[].stages[].slug` | str | 3/3 | play_ins ; swiss |
| `data.standings[].stages[].type` | NoneType | 0/3 |  |

## getTeams

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|
| `data.teams[].alternativeImage` | NoneType,str | 1325/1586 | https://lolstatic-a.akamaihd.net/esports ; https://lolstatic-a.akamaihd.net/esports |
| `data.teams[].backgroundImage` | NoneType,str | 111/1586 | https://lolstatic-a.akamaihd.net/esports ; https://lolstatic-a.akamaihd.net/esports |
| `data.teams[].code` | str | 1586/1586 | TBDD ; TBDA |
| `data.teams[].homeLeague` | NoneType | 0/737 |  |
| `data.teams[].homeLeague.name` | str | 849/849 | MSI ; LJL |
| `data.teams[].homeLeague.region` | str | 849/849 | 국제 대회 ; 일본 |
| `data.teams[].id` | str | 1586/1586 | 100205572995797818 ; 100205572997632804 |
| `data.teams[].image` | str | 1586/1586 | https://lolstatic-a.akamaihd.net/esports ; https://lolstatic-a.akamaihd.net/esports |
| `data.teams[].name` | str | 1586/1586 | TBD ; PENTAGRAM |
| `data.teams[].players[].firstName` | str | 5431/5431 | Shiro ; Yuta |
| `data.teams[].players[].id` | str | 5431/5431 | 100205572901889771 ; 98767975932435430 |
| `data.teams[].players[].image` | str | 5431/5431 | http://static.lolesports.com/players/168 ; https://lolstatic-a.akamaihd.net/esports |
| `data.teams[].players[].lastName` | str | 5431/5431 | Sasaki ; Noguchi |
| `data.teams[].players[].role` | str | 5431/5431 | top ; bottom |
| `data.teams[].players[].summonerName` | str | 5431/5431 | Paz ; Moyashi |
| `data.teams[].slug` | str | 1586/1586 | tbd ; pentagram |
| `data.teams[].status` | str | 1586/1586 | archived ; active |

## getTournamentsForLeague

| 경로 | 타입 | 채움률 | 예시 |
|---|---|---|---|
| `data.leagues[].tournaments[].endDate` | str | 11/11 | 2026-11-15 ; 2025-11-09 |
| `data.leagues[].tournaments[].id` | str | 11/11 | 115660540725177488 ; 113475452383887518 |
| `data.leagues[].tournaments[].slug` | str | 11/11 | worlds_2026 ; worlds_2025 |
| `data.leagues[].tournaments[].startDate` | str | 11/11 | 2026-10-15 ; 2025-10-14 |
