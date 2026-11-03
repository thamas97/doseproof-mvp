"""SQLite receipt storage for the collector's single writer.

write_raw commits before returning. Validation and normalization are subsequent
transactions so their failure cannot roll back the original receipt. These
functions are local Python interfaces, not HTTP or treatment-control routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Literal
from uuid import uuid4


MIGRATIONS = ('001_evidence.sql', '002_prevent_replacement.sql')
SCHEMA_VERSION = len(MIGRATIONS)
APPLICATION_ID = 0x44504D31  # DPM1; distinguish this database from unrelated files.
DEFAULT_DATABASE = Path('doseproof.db')


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _reject_constant(value: str) -> None:
    raise ValueError(f'Non-finite JSON value: {value}')


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def _decode(body: bytes) -> Any:
    # Parsing only happens after the original bytes have been committed.
    return json.loads(body.decode('utf-8'), parse_constant=_reject_constant, object_pairs_hook=_unique_keys)


@dataclass(frozen=True)
class RawReceipt:
    receipt_id: str
    received_at_utc: str
    body: bytes
    body_sha256: str
    content_type: str | None
    normalized_id: str | None


@dataclass(frozen=True)
class NormalizedWrite:
    outcome: Literal['created', 'duplicate', 'conflict']
    normalized_id: str | None
    error_id: str | None = None


def open_read_only(path: str | Path) -> sqlite3.Connection:
    """Open an existing database without creating it or permitting mutations."""
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA query_only = ON')
    return conn


class EvidenceStore:
    """One connection owned by one collector thread; do not share across threads."""

    def __init__(self, path: str | Path = DEFAULT_DATABASE):
        self.path = Path(path).resolve()
        if not self.path.parent.is_dir():
            raise FileNotFoundError(f'Database directory does not exist: {self.path.parent}')
        self._conn = sqlite3.connect(self.path, timeout=5)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute('PRAGMA foreign_keys = ON')
            self._conn.execute('PRAGMA synchronous = FULL')
            self._migrate()
        except BaseException:
            self._conn.close()
            raise

    def _migrate(self) -> None:
        # Serialize initialization, refuse unknown versions, and apply all DDL
        # atomically. Do not stamp an unrelated existing database as DoseProof.
        self._conn.execute('BEGIN IMMEDIATE')
        try:
            version = self._conn.execute('PRAGMA user_version').fetchone()[0]
            application_id = self._conn.execute('PRAGMA application_id').fetchone()[0]
            if not 0 <= version <= SCHEMA_VERSION:
                raise RuntimeError(f'Unsupported database schema version: {version}')
            if version:
                if application_id != APPLICATION_ID:
                    raise RuntimeError('Database is not identified as DoseProof MVP')
            else:
                if application_id not in (0, APPLICATION_ID):
                    raise RuntimeError('Database belongs to another application')
                if self._conn.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchone():
                    raise RuntimeError('Refusing to initialize a nonempty unversioned database')
                self._conn.execute(f'PRAGMA application_id = {APPLICATION_ID}')
            for filename in MIGRATIONS[version:]:
                migration = Path(__file__).with_name('migrations') / filename
                statement = ''
                for line in migration.read_text(encoding='utf-8').splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        self._conn.execute(statement)
                        statement = ''
                if statement.strip():
                    raise RuntimeError('Incomplete schema migration')
            if version < SCHEMA_VERSION:
                self._conn.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
            self._conn.commit()
        except BaseException:
            self._conn.rollback()
            raise

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EvidenceStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def write_raw(self, body: bytes, *, content_type: str | None = None) -> RawReceipt:
        """Durably retain every attempt, even malformed, empty or duplicate bytes."""
        if not isinstance(body, bytes):
            raise TypeError('Pass original bytes; do not parse or reserialize before write_raw')
        receipt = RawReceipt(str(uuid4()), _utc_now(), body, hashlib.sha256(body).hexdigest(), content_type, None)
        with self._conn:
            self._conn.execute(
                'INSERT INTO raw_events(receipt_id, received_at_utc, body, body_sha256, content_type) VALUES (?, ?, ?, ?, ?)',
                (receipt.receipt_id, receipt.received_at_utc, body, receipt.body_sha256, content_type),
            )
        return receipt

    def read_raw(self, receipt_id: str) -> RawReceipt | None:
        row = self._conn.execute('SELECT * FROM raw_events WHERE receipt_id = ?', (receipt_id,)).fetchone()
        return RawReceipt(**dict(row)) if row else None

    def write_validation_error(self, receipt_id: str, *, code: str, message: str, stage: str = 'validation') -> str:
        """Record a caller's actual finding; no error is inferred from arrival alone."""
        if not all(isinstance(v, str) and v.strip() for v in (code, message, stage)):
            raise ValueError('stage, code and message must be nonempty strings')
        with self._conn:
            return self._insert_error(receipt_id, code=code, message=message, stage=stage)

    def _insert_error(self, receipt_id: str, *, code: str, message: str, stage: str) -> str:
        error_id = str(uuid4())
        self._conn.execute(
            'INSERT INTO validation_errors VALUES (?, ?, ?, ?, ?, ?)',
            (error_id, receipt_id, _utc_now(), stage, code, message),
        )
        return error_id

    def write_normalized(self, receipt_id: str, validated_event: dict[str, Any]) -> NormalizedWrite:
        """Register an unchanged, externally validated v0.1 envelope once.

        This is NOT the layer-3 validator. It guards provenance and uniqueness.
        The caller must validate semantics/UTC/units first. Payload transformations
        need a reviewed extension; never overwrite the original envelope here.
        Identity is scoped to (run_id, source_id, event_id), proposed for team review.
        """
        receipt = self.read_raw(receipt_id)
        if receipt is None:
            raise KeyError(f'Unknown receipt: {receipt_id}')
        original = _decode(receipt.body)
        event_json = _canonical(validated_event)
        if not isinstance(original, dict) or event_json != _canonical(original):
            raise ValueError('Validated envelope must match the retained source JSON')
        required = ('run_id', 'source_id', 'event_id', 'source_timestamp_utc', 'emitted_at_utc')
        if not all(isinstance(validated_event.get(k), str) and validated_event[k] for k in required):
            raise ValueError('Source identity and timestamps must be nonempty strings')
        if 'change_id' not in validated_event or not (
            validated_event['change_id'] is None or isinstance(validated_event['change_id'], str)
        ):
            raise ValueError('change_id must be present and nullable text')
        identity = tuple(validated_event[k] for k in ('run_id', 'source_id', 'event_id'))
        self._conn.execute('BEGIN IMMEDIATE')
        try:
            existing = self._conn.execute(
                'SELECT normalized_id, event_json FROM normalized_events WHERE run_id = ? AND source_id = ? AND event_id = ?',
                identity,
            ).fetchone()
            if existing and existing['event_json'] != event_json:
                error_id = self._insert_error(
                    receipt_id, code='event_identity_conflict', stage='identity',
                    message='Source identity was reused with different content; existing evidence was retained',
                )
                result = NormalizedWrite('conflict', None, error_id)
            else:
                normalized_id = existing['normalized_id'] if existing else str(uuid4())
                if not existing:
                    self._conn.execute(
                        'INSERT INTO normalized_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (normalized_id, receipt_id, *identity, validated_event['source_timestamp_utc'],
                         validated_event['emitted_at_utc'], validated_event['change_id'], event_json),
                    )
                self._conn.execute(
                    'UPDATE raw_events SET normalized_id = ? WHERE receipt_id = ?',
                    (normalized_id, receipt_id),
                )
                result = NormalizedWrite('duplicate' if existing else 'created', normalized_id)
            self._conn.commit()
            return result
        except BaseException:
            self._conn.rollback()
            raise

    def read_normalized(self, normalized_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            'SELECT event_json FROM normalized_events WHERE normalized_id = ?', (normalized_id,),
        ).fetchone()
        return json.loads(row['event_json']) if row else None
