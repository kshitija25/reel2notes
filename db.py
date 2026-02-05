import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "data" / "reel2notes.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reels (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  downloaded_path TEXT,
  audio_path TEXT,
  model TEXT,
  language TEXT
);

CREATE TABLE IF NOT EXISTS transcripts (
  reel_id INTEGER PRIMARY KEY,
  raw_text TEXT,
  en_text TEXT,
  FOREIGN KEY(reel_id) REFERENCES reels(id)
);
"""

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)

def upsert_reel(url: str, downloaded_path: str | None, audio_path: str | None, model: str, language: str) -> int:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute(
            """INSERT INTO reels(url, created_at, downloaded_path, audio_path, model, language)
               VALUES(?, ?, ?, ?, ?, ?)
               ON CONFLICT(url) DO UPDATE SET
                 downloaded_path=excluded.downloaded_path,
                 audio_path=excluded.audio_path,
                 model=excluded.model,
                 language=excluded.language
            """,
            (url, now, downloaded_path, audio_path, model, language),
        )
        row = con.execute("SELECT id FROM reels WHERE url=?", (url,)).fetchone()
        return int(row[0])

def save_transcripts(reel_id: int, raw_text: str, en_text: str):
    with connect() as con:
        con.execute(
            """INSERT INTO transcripts(reel_id, raw_text, en_text)
               VALUES(?, ?, ?)
               ON CONFLICT(reel_id) DO UPDATE SET
                 raw_text=excluded.raw_text,
                 en_text=excluded.en_text
            """,
            (reel_id, raw_text, en_text),
        )
