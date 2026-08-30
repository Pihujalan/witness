"""
Hash-chained Audit Log
-----------------------
Every gateway decision - allowed, held, or blocked - is appended here.
Each entry stores a hash derived from the previous entry's hash plus
its own content, so altering any past entry breaks every hash after
it. That's a simple, honest form of tamper-evidence: it doesn't need
a blockchain, just a verifiable chain.

Backed by a real database (SQLite for local dev, Postgres in
production via DATABASE_URL) rather than an in-memory list or a flat
file. That choice is deliberate, not decorative: most free hosting
tiers wipe the filesystem on every redeploy or cold restart, and this
project's entire pitch is a ledger that can't quietly lose history -
so it can't be the thing that quietly resets every time the server
restarts. Point DATABASE_URL at a free hosted Postgres (Neon,
Supabase) for the live deployment; local dev needs no setup at all.

Honest scope note (state this in the README too): the hash chain
proves *internal* consistency - that no entry was altered after being
appended. It does not, by itself, prove the log wasn't truncated or
replaced wholesale; a production version would periodically anchor
checkpoints to a separate write-once store.
"""
from __future__ import annotations
import hashlib
import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData, select, func, update

GENESIS_HASH = "0" * 64


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


@dataclass
class AuditEntry:
    seq: int
    timestamp: str
    payload: dict
    prev_hash: str
    entry_hash: str


class AuditLog:
    def __init__(self, database_url: Optional[str] = None):
        database_url = database_url or os.environ.get("DATABASE_URL", "sqlite:///witness_audit.db")
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        self._lock = threading.Lock()
        metadata = MetaData()
        self._table = Table(
            "audit_entries", metadata,
            Column("seq", Integer, primary_key=True, autoincrement=False),
            Column("timestamp", String, nullable=False),
            Column("payload", String, nullable=False),
            Column("prev_hash", String, nullable=False),
            Column("entry_hash", String, nullable=False),
        )
        metadata.create_all(self._engine)

    def _row_to_entry(self, row) -> AuditEntry:
        return AuditEntry(
            seq=row.seq, timestamp=row.timestamp,
            payload=json.loads(row.payload), prev_hash=row.prev_hash, entry_hash=row.entry_hash,
        )

    def append(self, payload: dict) -> AuditEntry:
        with self._lock, self._engine.begin() as conn:
            last_seq = conn.execute(select(func.max(self._table.c.seq))).scalar()
            prev_hash = GENESIS_HASH
            if last_seq is not None:
                prev_row = conn.execute(select(self._table).where(self._table.c.seq == last_seq)).first()
                prev_hash = prev_row.entry_hash
            seq = 0 if last_seq is None else last_seq + 1

            timestamp = datetime.now(timezone.utc).isoformat()
            content = _canonical({"seq": seq, "timestamp": timestamp, "payload": payload, "prev_hash": prev_hash})
            entry_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

            conn.execute(self._table.insert().values(
                seq=seq, timestamp=timestamp, payload=_canonical(payload),
                prev_hash=prev_hash, entry_hash=entry_hash,
            ))
            return AuditEntry(seq=seq, timestamp=timestamp, payload=payload, prev_hash=prev_hash, entry_hash=entry_hash)

    def verify_chain(self) -> tuple[bool, Optional[int]]:
        prev_hash = GENESIS_HASH
        for entry in self.all_entries():
            content = _canonical({
                "seq": entry.seq, "timestamp": entry.timestamp,
                "payload": entry.payload, "prev_hash": prev_hash,
            })
            recomputed = hashlib.sha256(content.encode("utf-8")).hexdigest()
            if recomputed != entry.entry_hash or entry.prev_hash != prev_hash:
                return False, entry.seq
            prev_hash = entry.entry_hash
        return True, None

    def all_entries(self) -> list[AuditEntry]:
        with self._engine.begin() as conn:
            rows = conn.execute(select(self._table).order_by(self._table.c.seq)).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def tamper_for_demo(self, seq: int, new_payload: dict):
        """FOR THE LIVE DEMO ONLY: deliberately corrupts one entry so
        'Verify Log Integrity' has something real to catch."""
        with self._lock, self._engine.begin() as conn:
            conn.execute(
                update(self._table).where(self._table.c.seq == seq).values(payload=_canonical(new_payload))
            )
