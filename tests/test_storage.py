import json

from collectors.lolesports import LolEsportsCollector
from storage.db import RawResponse, connect, latest_raw, list_raw, save_raw


class FakeResp:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = responses
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.responses.pop(0)


def test_save_keeps_history():
    conn = connect(":memory:")
    raw = RawResponse("s", "getSchedule", {"hl": "ko-KR"}, "2026-10-15T00:00:00Z", 200, '{"a":1}')
    save_raw(conn, raw)
    save_raw(conn, RawResponse("s", "getSchedule", {"hl": "ko-KR"}, "2026-10-15T01:00:00Z", 200, '{"a":2}'))
    assert len(list_raw(conn)) == 2
    assert json.loads(latest_raw(conn, "s", "getSchedule", {"hl": "ko-KR"})["body_text"]) == {"a": 2}


def test_latest_ignores_errors():
    conn = connect(":memory:")
    save_raw(conn, RawResponse("s", "e", {}, "t1", 200, "ok"))
    save_raw(conn, RawResponse("s", "e", {}, "t2", 403, "err"))
    assert latest_raw(conn, "s", "e", {})["body_text"] == "ok"


def test_collector_stores_with_params_and_status():
    conn = connect(":memory:")
    session = FakeSession([FakeResp(200, '{"data":{}}'), FakeResp(403, "Forbidden")])
    c = LolEsportsCollector(api_key="k", session=session)
    c.fetch_and_store(conn, "getLeagues")
    _, raw = c.fetch_and_store(conn, "getSchedule", leagueId="1")
    assert raw.status_code == 403
    assert session.headers["x-api-key"] == "k"
    assert session.calls[1][1] == {"hl": "ko-KR", "leagueId": "1"}
    assert [r["status_code"] for r in list_raw(conn)] == [403, 200]
