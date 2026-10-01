from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
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
        connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS detection_reviews (
                    detection_id TEXT PRIMARY KEY REFERENCES detections(id),
                    review_json  TEXT NOT NULL,
                    updated_at   TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS detection_review_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    detection_id TEXT NOT NULL,
                    survey_id TEXT NOT NULL,
                    detection_json TEXT NOT NULL,
                    review_json TEXT NOT NULL,
                    archived_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processing_status (
                    survey_id TEXT PRIMARY KEY REFERENCES surveys(id),
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(surveys)")}
            if "extraction_json" not in columns:
                conn.execute("ALTER TABLE surveys ADD COLUMN extraction_json TEXT")

    def ensure_survey(self, survey_id: str, name: str | None = None) -> None:
        with self.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO surveys (id, name, created_at) VALUES (?, ?, ?)",
                (survey_id, name or survey_id, datetime.now(timezone.utc).isoformat()),
            )

    def save_ingest(self, survey_id: str, source_path: str, qc: dict, extraction: dict | None = None, name: str | None = None) -> None:
        self.ensure_survey(survey_id, name)
        with self.connection() as conn:
            conn.execute(
                "UPDATE surveys SET name=?, source_path=?, qc_json=?, extraction_json=? WHERE id=?",
                (name or survey_id, source_path, json.dumps(qc), json.dumps(extraction) if extraction else None, survey_id),
            )

    def surveys(self) -> list[dict]:
        """Return persisted mission metadata without exposing local file paths."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.name, s.created_at, s.qc_json, COUNT(d.id) AS detection_count
                FROM surveys AS s
                LEFT JOIN detections AS d ON d.survey_id = s.id
                GROUP BY s.id
                ORDER BY s.created_at DESC
                """
            ).fetchall()
        return [
            {
                "survey_id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "qc_report": json.loads(row["qc_json"]) if row["qc_json"] else None,
                "detection_count": row["detection_count"],
            }
            for row in rows
        ]

    def ingest_info(self, survey_id: str) -> tuple[str, dict, dict | None] | None:
        with self.connection() as conn:
            row = conn.execute("SELECT source_path, qc_json, extraction_json FROM surveys WHERE id=?", (survey_id,)).fetchone()
        if not row or not row["source_path"] or not row["qc_json"]:
            return None
        return row["source_path"], json.loads(row["qc_json"]), json.loads(row["extraction_json"]) if row["extraction_json"] else None

    def replace_detections(self, survey_id: str, detections: list[dict]) -> None:
        """Replace the active inference result while preserving reviewed history."""
        archived_at = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            reviewed = conn.execute(
                """
                SELECT d.id, d.payload_json, dr.review_json
                FROM detections AS d
                JOIN detection_reviews AS dr ON dr.detection_id = d.id
                WHERE d.survey_id = ?
                """,
                (survey_id,),
            ).fetchall()
            conn.executemany(
                """
                INSERT INTO detection_review_history
                    (detection_id, survey_id, detection_json, review_json, archived_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (row["id"], survey_id, row["payload_json"], row["review_json"], archived_at)
                    for row in reviewed
                ],
            )
            conn.execute(
                "DELETE FROM detection_reviews WHERE detection_id IN (SELECT id FROM detections WHERE survey_id=?)",
                (survey_id,),
            )
            conn.execute("DELETE FROM detections WHERE survey_id=?", (survey_id,))
            conn.executemany(
                "INSERT INTO detections (id, survey_id, payload_json) VALUES (?, ?, ?)",
                [(d["id"], survey_id, json.dumps(d)) for d in detections],
            )

    def detections_for_survey(self, survey_id: str) -> list[dict]:
        """Return active detections enriched with persisted operator reviews."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT d.payload_json, dr.review_json
                FROM detections AS d
                LEFT JOIN detection_reviews AS dr ON dr.detection_id = d.id
                WHERE d.survey_id = ?
                ORDER BY d.id
                """,
                (survey_id,),
            ).fetchall()
        detections = []
        for row in rows:
            detection = json.loads(row["payload_json"])
            detection["review"] = json.loads(row["review_json"]) if row["review_json"] else None
            detections.append(detection)
        return detections

    def review_history_for_survey(self, survey_id: str) -> list[dict]:
        """Return archived review decisions from previous processing runs."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT detection_id, detection_json, review_json, archived_at
                FROM detection_review_history
                WHERE survey_id = ?
                ORDER BY id
                """,
                (survey_id,),
            ).fetchall()
        return [
            {
                "detection_id": row["detection_id"],
                "detection": json.loads(row["detection_json"]),
                "review": json.loads(row["review_json"]),
                "archived_at": row["archived_at"],
            }
            for row in rows
        ]

    def save_processing_status(self, survey_id: str, payload: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO processing_status (survey_id, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(survey_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (survey_id, json.dumps(payload), now),
            )

    def get_processing_status(self, survey_id: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT payload_json FROM processing_status WHERE survey_id=?",
                (survey_id,),
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def detection(self, detection_id: str) -> dict | None:
        with self.connection() as conn:
            row = conn.execute("SELECT payload_json FROM detections WHERE id=?", (detection_id,)).fetchone()
        return json.loads(row["payload_json"]) if row else None

    # ------------------------------------------------------------------
    # Operator Review
    # ------------------------------------------------------------------

    def save_review(self, detection_id: str, review: dict) -> None:
        """Upsert an operator review for a detection.  Idempotent — calling
        again overwrites the previous decision."""
        now = datetime.now(timezone.utc).isoformat()
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO detection_reviews (detection_id, review_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(detection_id) DO UPDATE SET
                    review_json = excluded.review_json,
                    updated_at  = excluded.updated_at
                """,
                (detection_id, json.dumps(review), now),
            )

    def get_review(self, detection_id: str) -> dict | None:
        """Return the operator review for one detection, or None if unreviewed."""
        with self.connection() as conn:
            row = conn.execute(
                "SELECT review_json FROM detection_reviews WHERE detection_id=?",
                (detection_id,),
            ).fetchone()
        return json.loads(row["review_json"]) if row else None

    def delete_review(self, detection_id: str) -> bool:
        """Remove a review.  Returns True if a row was deleted."""
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM detection_reviews WHERE detection_id=?",
                (detection_id,),
            )
        return cursor.rowcount > 0

    def reviews_for_survey(self, survey_id: str) -> dict[str, dict]:
        """Return a mapping of detection_id → review_dict for all detections
        in a survey that have been reviewed.  Used by export endpoints."""
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT dr.detection_id, dr.review_json
                FROM detection_reviews dr
                JOIN detections d ON d.id = dr.detection_id
                WHERE d.survey_id = ?
                """,
                (survey_id,),
            ).fetchall()
        return {row["detection_id"]: json.loads(row["review_json"]) for row in rows}
