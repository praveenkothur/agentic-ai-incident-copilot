import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "audit.db"


def initialize() -> None:
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def record(incident_id: str, event_type: str, actor: str, details: dict) -> None:
    initialize()
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            """INSERT INTO audit_events
               (incident_id, event_type, actor, details)
               VALUES (?, ?, ?, ?)""",
            (incident_id, event_type, actor, json.dumps(details, default=str)),
        )


def get_events(incident_id: str) -> list[dict]:
    initialize()
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """SELECT event_type, actor, details, created_at
               FROM audit_events WHERE incident_id = ? ORDER BY id""",
            (incident_id,),
        ).fetchall()
    return [
        {"event_type": r[0], "actor": r[1], "details": json.loads(r[2]), "created_at": r[3]}
        for r in rows
    ]
