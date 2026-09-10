import json
import os
from itertools import chain

from utils.server_store import read_servers

DEFAULT_STATUSES_FILE = "data/default_statuses.json"
CUSTOM_STATUSES_FILE = "data/custom_statuses.json"
DEFAULT_STATUSES = [
    {"text": "Helping out {total_teams} teams", "enabled": True},
    {"text": "Managing in {servers} servers", "enabled": True},
    {"text": "Assisting {users} users", "enabled": True},
]


def ensure_status_files() -> None:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DEFAULT_STATUSES_FILE):
        with open(DEFAULT_STATUSES_FILE, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_STATUSES, handle, indent=4)


def _read_status_file(file_path: str) -> list[dict]:
    if not os.path.exists(file_path):
        return []

    with open(file_path, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            return []

    return data if isinstance(data, list) else []


def _write_status_file(file_path: str, entries: list[dict]) -> None:
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, indent=4)


def list_statuses() -> list[dict]:
    ensure_status_files()
    defaults = [
        {**entry, "source": "default"}
        for entry in _read_status_file(DEFAULT_STATUSES_FILE)
    ]
    custom = [
        {**entry, "source": "custom"}
        for entry in _read_status_file(CUSTOM_STATUSES_FILE)
    ]
    return list(chain(defaults, custom))


def get_enabled_statuses() -> list[dict]:
    statuses = [entry for entry in list_statuses() if entry.get("enabled", True) and entry.get("text")]
    return statuses or [{"text": "Helping out teams", "enabled": True, "source": "fallback"}]


def add_custom_status(text: str) -> tuple[bool, dict]:
    ensure_status_files()
    normalized = text.strip()
    if not normalized:
        raise ValueError("Status text cannot be empty.")

    custom = _read_status_file(CUSTOM_STATUSES_FILE)
    for entry in custom:
        if entry.get("text", "").casefold() == normalized.casefold():
            entry["enabled"] = True
            _write_status_file(CUSTOM_STATUSES_FILE, custom)
            return False, entry

    entry = {"text": normalized, "enabled": True}
    custom.append(entry)
    _write_status_file(CUSTOM_STATUSES_FILE, custom)
    return True, entry


def disable_status(text: str) -> dict | None:
    ensure_status_files()
    normalized = text.strip().casefold()
    if not normalized:
        return None

    for file_path, source in (
        (CUSTOM_STATUSES_FILE, "custom"),
        (DEFAULT_STATUSES_FILE, "default"),
    ):
        entries = _read_status_file(file_path)
        for entry in entries:
            if entry.get("text", "").casefold() == normalized:
                entry["enabled"] = False
                _write_status_file(file_path, entries)
                return {**entry, "source": source}
    return None


def render_status(text: str, bot) -> str:
    servers = len(bot.guilds)
    users = len(set(bot.get_all_members()))
    total_teams = sum(len(server.get("teams", [])) for server in read_servers().values())
    return (
        text.replace("{users}", str(users))
        .replace("{servers}", str(servers))
        .replace("{total_teams}", str(total_teams))
    )
