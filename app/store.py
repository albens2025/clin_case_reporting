from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import ConversationMessage, InterviewState, utcnow_iso


class SessionStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    phone_number TEXT PRIMARY KEY,
                    phase TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    notes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )

    def get_or_create_state(self, phone_number: str) -> InterviewState:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE phone_number = ?", (phone_number,)
            ).fetchone()

            if row:
                record = {
                    "phone_number": row["phone_number"],
                    "phase": row["phase"],
                    "urgency": row["urgency"],
                    "notes": json.loads(row["notes_json"]),
                }
                return InterviewState.from_record(record)

            now = utcnow_iso()
            state = InterviewState(phone_number=phone_number)
            conn.execute(
                """
                INSERT INTO sessions (
                    phone_number, phase, urgency, notes_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    state.phone_number,
                    state.phase,
                    state.urgency,
                    json.dumps(state.notes),
                    now,
                    now,
                ),
            )
            return state

    def save_state(self, state: InterviewState) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET phase = ?, urgency = ?, notes_json = ?, updated_at = ?
                WHERE phone_number = ?
                """,
                (
                    state.phase,
                    state.urgency,
                    json.dumps(state.notes),
                    utcnow_iso(),
                    state.phone_number,
                ),
            )

    def append_message(self, phone_number: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (phone_number, role, content, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (phone_number, role, content, utcnow_iso()),
            )

    def recent_messages(
        self, phone_number: str, limit: int = 16
    ) -> list[ConversationMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, timestamp
                FROM messages
                WHERE phone_number = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (phone_number, limit),
            ).fetchall()

        rows = list(reversed(rows))
        return [
            ConversationMessage(
                role=row["role"],
                content=row["content"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]
