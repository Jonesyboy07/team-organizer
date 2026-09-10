import json
import os
import sqlite3
from datetime import datetime, timezone
from os import path

SERVERS_FILE = "data/servers.json"
DB_FILE = "data/storage.db"
MIGRATION_KEY = "servers_json_migrated"
BANNED_SERVERS_KEY = "banned_servers"


def _normalize_guild_id(guild_id) -> str:
    return str(guild_id)


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_FILE)


def _create_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS servers (
            guild_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )


def _get_metadata(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set_metadata(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        "INSERT INTO metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _load_json_metadata(connection: sqlite3.Connection, key: str, default):
    raw = _get_metadata(connection, key)
    if raw is None:
        return default
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return parsed


def _save_json_metadata(connection: sqlite3.Connection, key: str, value) -> None:
    _set_metadata(connection, key, json.dumps(value))


def _load_servers_backup() -> dict:
    if not path.exists(SERVERS_FILE):
        return {}

    with open(SERVERS_FILE, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


def initialize_storage(logger=None) -> bool:
    os.makedirs("data", exist_ok=True)

    migrated = False
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _create_tables(connection)
        if _get_metadata(connection, MIGRATION_KEY) is None:
            existing_rows = connection.execute("SELECT COUNT(*) FROM servers").fetchone()[0]
            if existing_rows == 0:
                backup_data = _load_servers_backup()
                for guild_id, server_data in backup_data.items():
                    connection.execute(
                        "INSERT OR REPLACE INTO servers(guild_id, data) VALUES(?, ?)",
                        (str(guild_id), json.dumps(server_data)),
                    )
            _set_metadata(
                connection,
                MIGRATION_KEY,
                datetime.now(timezone.utc).isoformat(),
            )
            migrated = True

    if migrated and logger is not None:
        logger(
            f"Migrated {len(_load_servers_backup())} server record(s) from {SERVERS_FILE} "
            f"into {DB_FILE}. JSON backups were kept unchanged."
        )
    return migrated


def read_servers() -> dict:
    initialize_storage()
    with _connect() as connection:
        _create_tables(connection)
        rows = connection.execute("SELECT guild_id, data FROM servers").fetchall()
    data = {}
    for guild_id, payload in rows:
        try:
            data[guild_id] = json.loads(payload)
        except json.JSONDecodeError:
            continue
    return data


def write_servers(data: dict, indent: int = 4) -> None:
    del indent
    initialize_storage()
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        desired_ids = {_normalize_guild_id(guild_id) for guild_id in data}
        existing_ids = {
            row[0]
            for row in connection.execute("SELECT guild_id FROM servers").fetchall()
        }
        stale_ids = existing_ids - desired_ids
        if stale_ids:
            connection.executemany(
                "DELETE FROM servers WHERE guild_id = ?",
                [(guild_id,) for guild_id in stale_ids],
            )
        connection.executemany(
            "INSERT INTO servers(guild_id, data) VALUES(?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET data = excluded.data",
            [
                (_normalize_guild_id(guild_id), json.dumps(server_data))
                for guild_id, server_data in data.items()
            ],
        )


def get_server(guild_id) -> dict:
    initialize_storage()
    gid = _normalize_guild_id(guild_id)
    with _connect() as connection:
        _create_tables(connection)
        row = connection.execute("SELECT data FROM servers WHERE guild_id = ?", (gid,)).fetchone()
    if row is None:
        return {}
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return {}


def set_server(guild_id, server_data: dict) -> None:
    initialize_storage()
    gid = _normalize_guild_id(guild_id)
    with _connect() as connection:
        _create_tables(connection)
        connection.execute(
            "INSERT INTO servers(guild_id, data) VALUES(?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET data = excluded.data",
            (gid, json.dumps(server_data)),
        )


def is_setup_complete(guild_id) -> bool:
    return get_server(guild_id).get("SetupComplete", False)


def get_teams(guild_id) -> list:
    return get_server(guild_id).get("teams", [])


def save_teams(guild_id, teams: list) -> None:
    gid = _normalize_guild_id(guild_id)
    data = read_servers()
    server_data = data.get(gid, {})
    server_data["teams"] = teams
    data[gid] = server_data
    write_servers(data)


def set_team_creation_blacklist(guild_id, blacklisted: bool = True) -> None:
    server_data = get_server(guild_id)
    server_data["team_creation_blacklisted"] = bool(blacklisted)
    set_server(guild_id, server_data)


def is_team_creation_blacklisted(guild_id) -> bool:
    return bool(get_server(guild_id).get("team_creation_blacklisted", False))


def get_banned_server_ids() -> set[str]:
    initialize_storage()
    with _connect() as connection:
        _create_tables(connection)
        stored = _load_json_metadata(connection, BANNED_SERVERS_KEY, [])
    if not isinstance(stored, list):
        return set()
    return {str(value) for value in stored}


def ban_server(guild_id) -> None:
    initialize_storage()
    gid = _normalize_guild_id(guild_id)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _create_tables(connection)
        stored = _load_json_metadata(connection, BANNED_SERVERS_KEY, [])
        if not isinstance(stored, list):
            stored = []
        banned = {str(value) for value in stored}
        banned.add(gid)
        _save_json_metadata(connection, BANNED_SERVERS_KEY, sorted(banned))


def is_server_banned(guild_id) -> bool:
    return _normalize_guild_id(guild_id) in get_banned_server_ids()
