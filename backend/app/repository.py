from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Repository:
    """SQLite adapter; service code does not know the persistence implementation."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS surveys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    source_path TEXT,
                    qc_json TEXT,
                    extraction_json TEXT
                );
                CREATE TABLE IF NOT EXISTS detections (
                    id TEXT PRIMARY KEY,
                    survey_id TEXT NOT NULL REFERENCES surveys(id),
                    payload_json TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(surveys)")}
            if "extraction_json" not in columns:
                conn.execute("ALTER TABLE surveys ADD COLUMN extraction_json TEXT")

    def ensure_survey(self, survey_id: str) -> None:
        from datetime import datetime, timezone
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO surveys (id, name, created_at) VALUES (?, ?, ?)",
                (survey_id, survey_id, datetime.now(timezone.utc).isoformat()),
            )

    def save_ingest(self, survey_id: str, source_path: str, qc: dict, extraction: dict | None = None) -> None:
        self.ensure_survey(survey_id)
        with self.connection() as conn:
            conn.execute("UPDATE surveys SET source_path=?, qc_json=?, extraction_json=? WHERE id=?", (source_path, json.dumps(qc), json.dumps(extraction) if extraction else None, survey_id))

    def ingest_info(self, survey_id: str) -> tuple[str, dict, dict | None] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT source_path, qc_json, extraction_json FROM surveys WHERE id=?", (survey_id,)).fetchone()
        if not row or not row["source_path"] or not row["qc_json"]:
            return None
        return row["source_path"], json.loads(row["qc_json"]), json.loads(row["extraction_json"]) if row["extraction_json"] else None

    def replace_detections(self, survey_id: str, detections: list[dict]) -> None:
        with self.connection() as conn:
            conn.execute("DELETE FROM detections WHERE survey_id=?", (survey_id,))
            conn.executemany(
                "INSERT INTO detections (id, survey_id, payload_json) VALUES (?, ?, ?)",
                [(d["id"], survey_id, json.dumps(d)) for d in detections],
            )

    def detections_for_survey(self, survey_id: str) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute("SELECT payload_json FROM detections WHERE survey_id=? ORDER BY id", (survey_id,)).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def detection(self, detection_id: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT payload_json FROM detections WHERE id=?", (detection_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None
