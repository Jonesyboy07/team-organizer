import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from utils.server_store import DB_FILE, initialize_storage


@contextmanager
def _connect():
    connection = sqlite3.connect(DB_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_queue() -> None:
    initialize_storage()
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS website_actions (
                action_id TEXT PRIMARY KEY,
                guild_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS website_runtime (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )


def write_runtime_snapshot(
    started_at: str,
    guild_count: int,
    guild_catalog: list[dict] | None = None,
    guilds: list[dict] | None = None,
) -> None:
    initialize_queue()
    snapshot = {
        "started_at": started_at,
        "guild_count": int(guild_count),
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
        "guild_catalog": guild_catalog or [],
        "guilds": guilds or [],
    }
    with _connect() as connection:
        connection.execute(
            "INSERT INTO website_runtime(key, value) VALUES ('bot', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(snapshot),),
        )


def read_runtime_snapshot() -> dict | None:
    initialize_queue()
    with _connect() as connection:
        row = connection.execute("SELECT value FROM website_runtime WHERE key = 'bot'").fetchone()
    return json.loads(row[0]) if row else None


def enqueue_action(guild_id: str, user_id: str, action_type: str, payload: dict) -> str:
    initialize_queue()
    action_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """INSERT INTO website_actions
               (action_id, guild_id, user_id, action_type, payload, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (action_id, str(guild_id), str(user_id), action_type, json.dumps(payload), now, now),
        )
    return action_id


def claim_next_action() -> dict | None:
    initialize_queue()
    now = datetime.now(timezone.utc)
    stale_before = (now - timedelta(minutes=5)).isoformat()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE website_actions SET status = 'pending', updated_at = ? "
            "WHERE status = 'running' AND updated_at < ?",
            (now.isoformat(), stale_before),
        )
        row = connection.execute(
            "SELECT * FROM website_actions WHERE status = 'pending' ORDER BY created_at LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        connection.execute(
            "UPDATE website_actions SET status = 'running', updated_at = ? WHERE action_id = ?",
            (now.isoformat(), row['action_id']),
        )
    action = dict(row)
    action['payload'] = json.loads(action['payload'])
    action['status'] = 'running'
    return action


def finish_action(action_id: str, status: str, result: str) -> None:
    if status not in {'completed', 'failed'}:
        raise ValueError("Action status must be 'completed' or 'failed'.")
    initialize_queue()
    with _connect() as connection:
        connection.execute(
            "UPDATE website_actions SET status = ?, result = ?, updated_at = ? WHERE action_id = ?",
            (status, result[:1000], datetime.now(timezone.utc).isoformat(), action_id),
        )


def list_user_actions(user_id: str, guild_ids: set[str], limit: int = 20) -> list[dict]:
    initialize_queue()
    if not guild_ids:
        return []
    placeholders = ','.join('?' for _ in guild_ids)
    with _connect() as connection:
        rows = connection.execute(
            f"SELECT action_id, guild_id, action_type, status, result, created_at, updated_at "
            f"FROM website_actions WHERE user_id = ? AND guild_id IN ({placeholders}) "
            "ORDER BY created_at DESC LIMIT ?",
            (str(user_id), *sorted(guild_ids), max(1, min(limit, 50))),
        ).fetchall()
    return [dict(row) for row in rows]