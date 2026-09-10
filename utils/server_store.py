import json
import os
import sqlite3
from datetime import datetime, timezone
from os import path

SERVERS_FILE = "data/servers.json"
DB_FILE = "data/storage.db"
MIGRATION_KEY = "servers_json_migrated"


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
        _create_tables(connection)
        if _get_metadata(connection, MIGRATION_KEY) is None:
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
    return {
        guild_id: json.loads(payload)
        for guild_id, payload in rows
    }


def write_servers(data: dict, indent: int = 4) -> None:
    del indent
    initialize_storage()
    with _connect() as connection:
        _create_tables(connection)
        connection.execute("DELETE FROM servers")
        connection.executemany(
            "INSERT INTO servers(guild_id, data) VALUES(?, ?)",
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
    return json.loads(row[0])


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
