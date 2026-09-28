import base64
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from flask import current_app

from utils.server_store import DB_FILE
from utils.website_queue import initialize_queue

SESSION_TTL = timedelta(days=90)


def _fernet():
    from cryptography.fernet import Fernet

    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def _serialize(data: dict) -> str:
    stored = dict(data)
    tokens = {key: stored.pop(key) for key in ("access_token", "refresh_token")}
    stored["oauth_tokens"] = _fernet().encrypt(json.dumps(tokens).encode("utf-8")).decode("ascii")
    return json.dumps(stored)


def _deserialize(raw: str) -> dict | None:
    stored = json.loads(raw)
    encrypted = stored.pop("oauth_tokens")
    try:
        from cryptography.fernet import InvalidToken

        stored.update(json.loads(_fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")))
    except ImportError:
        return None
    except InvalidToken:
        return None
    return stored


@contextmanager
def _connection():
    connection = sqlite3.connect(DB_FILE, timeout=10)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_session(user: dict, oauth: dict, guilds: list[dict]) -> tuple[str, str]:
    initialize_queue()
    session_id = uuid.uuid4().hex + uuid.uuid4().hex
    csrf_token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    payload = {
        "user": user,
        "access_token": oauth["access_token"],
        "refresh_token": oauth["refresh_token"],
        "access_expires_at": (now + timedelta(seconds=int(oauth.get("expires_in", 3600)))).isoformat(),
        "guilds": guilds,
        "guilds_updated_at": now.isoformat(),
        "csrf_token": csrf_token,
    }
    with _connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS website_sessions (session_id TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at TEXT NOT NULL)"
        )
        connection.execute("DELETE FROM website_sessions WHERE expires_at < ?", (now.isoformat(),))
        connection.execute(
            "INSERT INTO website_sessions(session_id, data, expires_at) VALUES (?, ?, ?)",
            (session_id, _serialize(payload), (now + SESSION_TTL).isoformat()),
        )
    return session_id, csrf_token


def get_session(session_id: str | None) -> dict | None:
    if not session_id:
        return None
    initialize_queue()
    with _connection() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS website_sessions (session_id TEXT PRIMARY KEY, data TEXT NOT NULL, expires_at TEXT NOT NULL)"
        )
        row = connection.execute(
            "SELECT data FROM website_sessions WHERE session_id = ? AND expires_at > ?",
            (session_id, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        if row:
            connection.execute(
                "UPDATE website_sessions SET expires_at = ? WHERE session_id = ?",
                ((datetime.now(timezone.utc) + SESSION_TTL).isoformat(), session_id),
            )
    return _deserialize(row[0]) if row else None


def update_session(session_id: str, data: dict) -> None:
    initialize_queue()
    with _connection() as connection:
        connection.execute(
            "UPDATE website_sessions SET data = ?, expires_at = ? WHERE session_id = ?",
            (
                _serialize(data),
                (datetime.now(timezone.utc) + SESSION_TTL).isoformat(),
                session_id,
            ),
        )


def delete_session(session_id: str | None) -> None:
    if not session_id:
        return
    initialize_queue()
    with _connection() as connection:
        connection.execute("DELETE FROM website_sessions WHERE session_id = ?", (session_id,))