"""Append-only SQLite evidence ledger."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import canonical_json, digest, utc_now


class EvidenceLedger:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL UNIQUE,
                record_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._db.commit()

    def append(
        self,
        record_id: str,
        record_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
    ) -> str:
        encoded = canonical_json(payload)
        payload_hash = digest(payload)
        try:
            self._db.execute(
                "INSERT INTO ledger(record_id,record_type,aggregate_id,payload_json,payload_hash,created_at) VALUES(?,?,?,?,?,?)",
                (record_id, record_type, aggregate_id, encoded, payload_hash, utc_now()),
            )
            self._db.commit()
        except sqlite3.IntegrityError:
            row = self._db.execute(
                "SELECT payload_hash FROM ledger WHERE record_id=?", (record_id,)
            ).fetchone()
            if row is None or row["payload_hash"] != payload_hash:
                raise ValueError(f"record {record_id!r} already exists with different content")
        return payload_hash

    def get(self, record_id: str) -> dict[str, Any] | None:
        row = self._db.execute("SELECT * FROM ledger WHERE record_id=?", (record_id,)).fetchone()
        return self._row(row) if row else None

    def records(self, *, record_type: str | None = None, aggregate_id: str | None = None) -> tuple[dict[str, Any], ...]:
        query = "SELECT * FROM ledger WHERE 1=1"
        params: list[Any] = []
        if record_type is not None:
            query += " AND record_type=?"
            params.append(record_type)
        if aggregate_id is not None:
            query += " AND aggregate_id=?"
            params.append(aggregate_id)
        query += " ORDER BY seq"
        return tuple(self._row(row) for row in self._db.execute(query, params).fetchall())

    def verify_integrity(self, *, aggregate_id: str | None = None) -> tuple[str, ...]:
        """Recompute content digests for an evidence scope without mutating it."""
        errors: list[str] = []
        for record in self.records(aggregate_id=aggregate_id):
            expected = digest(record["payload"])
            if expected != record["payload_hash"]:
                errors.append(f"{record['record_id']}: payload hash mismatch")
        return tuple(errors)

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "seq": row["seq"],
            "record_id": row["record_id"],
            "record_type": row["record_type"],
            "aggregate_id": row["aggregate_id"],
            "payload": json.loads(row["payload_json"]),
            "payload_hash": row["payload_hash"],
            "created_at": row["created_at"],
        }
