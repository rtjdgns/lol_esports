import json
from pathlib import Path

from collectors.lolesports import parse_schedule_events
from engine.series import series_status
from engine.swiss import load_rules, team_status
from models.schema import Match, SeriesTeam


def make(state, bo, wa, wb):
    return Match("1", "worlds", "x", "t", state, bo, (SeriesTeam("A", "A", wa), SeriesTeam("B", "B", wb)))


def test_series_phrases():
    assert series_status(make("inProgress", 5, 2, 1)) == "A 2 : B 1 · A팀 1승 남음"
    assert series_status(make("inProgress", 5, 2, 2)) == "A 2 : B 2 · 마지막 세트"
    assert series_status(make("inProgress", 3, 1, 1)) == "A 1 : B 1 · 마지막 세트"
    assert series_status(make("inProgress", 5, 1, 0)) == "A 1 : B 0 · A팀 2승 남음"
    assert series_status(make("inProgress", 5, 0, 0)) == "A vs B · 1세트 진행 중"
    assert series_status(make("unstarted", 3, 0, 0)) == "A vs B · Bo3"
    assert series_status(make("completed", 3, 2, 1)) == "A 2 : B 1 · A 승"


def test_swiss_status():
    assert team_status(3, 1) == "진출 확정"
    assert team_status(1, 3) == "탈락 확정"
    assert "진출 결정전" in team_status(2, 1)
    assert "탈락 결정전" in team_status(1, 2)


def test_rules_load():
    assert load_rules()["swiss"]["win_target"] == 3


def test_parse_real_sample():
    path = Path(__file__).resolve().parent.parent / "data" / "raw_samples" / "getSchedule.json"
    events = json.loads(path.read_text(encoding="utf-8"))["data"]["schedule"]["events"]
    matches = parse_schedule_events(events)
    assert len(matches) == len(events)
    assert all(series_status(m) for m in matches)
