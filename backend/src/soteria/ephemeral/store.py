from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from soteria.ephemeral.config import EphemeralConfig
from soteria.ephemeral.errors import NotFoundError
from soteria.ephemeral.models import (
    AccountAttachment,
    DeletionAuditRow,
    DeletionResult,
    EphemeralSessionRecord,
    SignupToken,
)
from soteria.extraction import ExtractionResult

_UPLOADED_POLICY_ARTIFACT = "uploaded_policy.pdf"


class EphemeralStore:
    def __init__(self, config: EphemeralConfig) -> None:
        self.config = config
        self.config.ephemeral_data_dir.mkdir(parents=True, exist_ok=True)
        self.config.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def create_anonymous_session(
        self,
        *,
        session_token: str,
        ip_address: str,
        filename: str,
        pdf_bytes: bytes,
        document_text: str,
        analysis: ExtractionResult,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        artifact_path = self._write_document_artifact(
            session_token=session_token,
            pdf_bytes=pdf_bytes,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO anonymous_sessions (
                  session_token, account_id, ip_address, filename, artifact_path,
                  document_text, analysis_json, created_at, expires_at
                )
                VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_token,
                    ip_address,
                    filename,
                    str(artifact_path),
                    document_text,
                    json.dumps(analysis.json),
                    _format_dt(created_at),
                    _format_dt(expires_at),
                ),
            )

    def get_session(
        self,
        session_token: str,
        *,
        now: datetime,
    ) -> EphemeralSessionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session_token, artifact_path, analysis_json, document_text,
                       expires_at, account_id
                FROM anonymous_sessions
                WHERE session_token = ?
                """,
                (session_token,),
            ).fetchone()
        if row is None:
            return None
        record = _record_from_row(row)
        if record.expires_at is not None and record.expires_at <= now:
            return None
        return record

    def raw_session_exists(self, session_token: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM anonymous_sessions WHERE session_token = ?",
                (session_token,),
            ).fetchone()
        return row is not None

    def create_signup_token(self, *, token: SignupToken, created_at: datetime) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO signup_tokens (
                  token, email, session_token, created_at, expires_at, consumed_at
                )
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    token.token,
                    token.email,
                    token.session_token,
                    _format_dt(created_at),
                    _format_dt(token.expires_at),
                ),
            )

    def consume_signup_token(self, *, token: str, now: datetime) -> AccountAttachment:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT token, email, session_token, expires_at, consumed_at
                FROM signup_tokens
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
            if row is None:
                raise NotFoundError("Signup token not found.")
            if row["consumed_at"] is not None or _parse_dt(row["expires_at"]) <= now:
                raise NotFoundError("Signup token is not available.")

            session_row = connection.execute(
                "SELECT session_token FROM anonymous_sessions WHERE session_token = ?",
                (row["session_token"],),
            ).fetchone()
            if session_row is None:
                raise NotFoundError("Ephemeral session not found.")

            account_id = uuid4().hex
            connection.execute(
                "INSERT INTO accounts (account_id, email, created_at) VALUES (?, ?, ?)",
                (account_id, row["email"], _format_dt(now)),
            )
            connection.execute(
                """
                UPDATE anonymous_sessions
                SET account_id = ?, expires_at = NULL
                WHERE session_token = ?
                """,
                (account_id, row["session_token"]),
            )
            connection.execute(
                "UPDATE signup_tokens SET consumed_at = ? WHERE token = ?",
                (_format_dt(now), token),
            )

        return AccountAttachment(
            account_id=account_id,
            email=row["email"],
            session_token=row["session_token"],
        )

    def get_account_session(
        self,
        account_id: str,
        session_token: str,
        *,
        now: datetime,
    ) -> EphemeralSessionRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session_token, artifact_path, analysis_json, document_text,
                       expires_at, account_id
                FROM anonymous_sessions
                WHERE account_id = ? AND session_token = ?
                """,
                (account_id, session_token),
            ).fetchone()
        if row is None:
            return None
        record = _record_from_row(row)
        if record.expires_at is not None and record.expires_at <= now:
            return None
        return record

    def delete_expired(self, *, now: datetime) -> DeletionResult:
        deleted_artifacts: list[str] = []
        deleted_sessions = 0
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_token, artifact_path
                FROM anonymous_sessions
                WHERE account_id IS NULL
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                """,
                (_format_dt(now),),
            ).fetchall()

            for row in rows:
                artifact_path = Path(row["artifact_path"])
                if artifact_path.exists():
                    artifact_path.unlink()
                    deleted_artifacts.append(str(artifact_path))
                connection.execute(
                    "DELETE FROM anonymous_sessions WHERE session_token = ?",
                    (row["session_token"],),
                )
                connection.execute(
                    """
                    INSERT INTO deletion_audit (
                      session_token, deleted_at, deleted_records, deleted_artifacts, reason
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["session_token"],
                        _format_dt(now),
                        json.dumps(["anonymous_sessions"]),
                        json.dumps([str(artifact_path)]),
                        "ttl_expired",
                    ),
                )
                deleted_sessions += 1
        return DeletionResult(
            deleted_sessions=deleted_sessions,
            deleted_artifacts=deleted_artifacts,
        )

    def list_deletion_audit(self) -> list[DeletionAuditRow]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_token, deleted_at, deleted_records, deleted_artifacts, reason
                FROM deletion_audit
                ORDER BY id
                """
            ).fetchall()
        return [
            DeletionAuditRow(
                session_token=row["session_token"],
                deleted_at=_parse_dt(row["deleted_at"]),
                deleted_records=json.loads(row["deleted_records"]),
                deleted_artifacts=json.loads(row["deleted_artifacts"]),
                reason=row["reason"],
            )
            for row in rows
        ]

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS anonymous_sessions (
                  session_token TEXT PRIMARY KEY,
                  account_id TEXT NULL,
                  ip_address TEXT NOT NULL,
                  filename TEXT NOT NULL,
                  artifact_path TEXT NOT NULL,
                  document_text TEXT NOT NULL,
                  analysis_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NULL
                );

                CREATE TABLE IF NOT EXISTS accounts (
                  account_id TEXT PRIMARY KEY,
                  email TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS signup_tokens (
                  token TEXT PRIMARY KEY,
                  email TEXT NOT NULL,
                  session_token TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL,
                  consumed_at TEXT NULL
                );

                CREATE TABLE IF NOT EXISTS deletion_audit (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_token TEXT NOT NULL,
                  deleted_at TEXT NOT NULL,
                  deleted_records TEXT NOT NULL,
                  deleted_artifacts TEXT NOT NULL,
                  reason TEXT NOT NULL
                );
                """
            )

    def _write_document_artifact(
        self,
        *,
        session_token: str,
        pdf_bytes: bytes,
    ) -> Path:
        session_dir = self.config.ephemeral_data_dir / "sessions" / session_token
        session_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = session_dir / _UPLOADED_POLICY_ARTIFACT
        artifact_path.write_bytes(pdf_bytes)
        return artifact_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.config.database_path)
        connection.row_factory = sqlite3.Row
        return connection


def _record_from_row(row: sqlite3.Row) -> EphemeralSessionRecord:
    return EphemeralSessionRecord(
        session_token=row["session_token"],
        artifact_path=Path(row["artifact_path"]),
        analysis_json=row["analysis_json"],
        document_text=row["document_text"],
        expires_at=_parse_optional_dt(row["expires_at"]),
        account_id=row["account_id"],
    )


def _format_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_optional_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _parse_dt(value)


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
