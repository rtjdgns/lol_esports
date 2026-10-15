import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "lol_esports.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    params_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    body_text TEXT NOT NULL,
    body_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_raw_lookup ON raw_responses (source, endpoint, fetched_at);
"""


@dataclass(frozen=True)
class RawResponse:
    source: str
    endpoint: str
    params: dict
    fetched_at: str
    status_code: int
    body_text: str


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path=DEFAULT_DB):
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_raw(conn, raw: RawResponse):
    digest = hashlib.sha256(raw.body_text.encode("utf-8")).hexdigest()
    cur = conn.execute(
        "INSERT INTO raw_responses (source, endpoint, params_json, fetched_at, status_code, body_text, body_sha256)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (raw.source, raw.endpoint, json.dumps(raw.params, sort_keys=True, ensure_ascii=False),
         raw.fetched_at, raw.status_code, raw.body_text, digest),
    )
    conn.commit()
    return cur.lastrowid


def latest_raw(conn, source, endpoint, params=None):
    params_json = json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    return conn.execute(
        "SELECT * FROM raw_responses WHERE source=? AND endpoint=? AND params_json=? AND status_code=200"
        " ORDER BY id DESC LIMIT 1",
        (source, endpoint, params_json),
    ).fetchone()


def list_raw(conn, limit=20):
    return conn.execute(
        "SELECT id, source, endpoint, params_json, fetched_at, status_code, length(body_text) AS bytes,"
        " substr(body_sha256, 1, 8) AS sha FROM raw_responses ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
