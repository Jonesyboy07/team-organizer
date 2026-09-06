import json
import os
from datetime import datetime, timezone
from os import makedirs, path


GAMES_FILE = "data/games.json"
SUGGESTION_GUILD_ID = int(os.getenv("SUGGESTION_GUILD_ID", "1427267917396840490"))
SUGGESTION_CHANNEL_ID = int(os.getenv("SUGGESTION_CHANNEL_ID", "1546032435786154054"))
SUGGESTION_PING_USER_ID = int(os.getenv("SUGGESTION_PING_USER_ID", "950380630905069578"))
SUGGESTION_COOLDOWN_SECONDS = 24 * 60 * 60

DEFAULT_GAMES = [
    {"id": "vr_pavlov_pc", "name": "Pavlov PC", "category": "VR", "enabled": True},
    {"id": "vr_pavlov_shack", "name": "Pavlov Shack", "category": "VR", "enabled": True},
    {"id": "vr_vail", "name": "Vail", "category": "VR", "enabled": True},
    {"id": "vr_breachers", "name": "Breachers", "category": "VR", "enabled": True},
    {"id": "vr_orion_drift", "name": "Orion Drift", "category": "VR", "enabled": True},
    {"id": "vr_onward", "name": "Onward", "category": "VR", "enabled": True},
    {"id": "vr_snapshot", "name": "Snapshot", "category": "VR", "enabled": True},
]


def _default_catalog() -> dict:
    return {
        "games": DEFAULT_GAMES,
        "suggestions": [],
        "suggestion_blacklist": [],
        "suggestion_cooldowns": {},
    }


def _read_catalog() -> dict:
    if not path.exists(GAMES_FILE):
        return _default_catalog()
    with open(GAMES_FILE, "r") as handle:
        data = json.load(handle)
    defaults = _default_catalog()
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def _write_catalog(catalog: dict) -> None:
    makedirs(path.dirname(GAMES_FILE), exist_ok=True)
    with open(GAMES_FILE, "w") as handle:
        json.dump(catalog, handle, indent=4)


def get_games() -> list[dict]:
    return _read_catalog()["games"]


def get_game(game_id: str) -> dict | None:
    normalized_id = game_id.strip().lower()
    return next((game for game in get_games() if game["id"] == normalized_id and game.get("enabled", True)), None)


def get_game_name(game_id: str) -> str:
    game = get_game(game_id)
    return game["name"] if game else "Unknown game"


def is_suggestion_blacklisted(user_id: int) -> bool:
    return user_id in _read_catalog()["suggestion_blacklist"]


def blacklist_suggester(user_id: int) -> None:
    catalog = _read_catalog()
    if user_id not in catalog["suggestion_blacklist"]:
        catalog["suggestion_blacklist"].append(user_id)
        _write_catalog(catalog)


def suggestion_cooldown_remaining(user_id: int, now: datetime | None = None) -> int:
    catalog = _read_catalog()
    timestamp = catalog["suggestion_cooldowns"].get(str(user_id))
    if timestamp is None:
        return 0
    now = now or datetime.now(timezone.utc)
    elapsed = (now - datetime.fromisoformat(timestamp)).total_seconds()
    return max(0, int(SUGGESTION_COOLDOWN_SECONDS - elapsed))


def add_suggestion(user_id: int, game_name: str) -> dict:
    catalog = _read_catalog()
    now = datetime.now(timezone.utc)
    suggestion = {
        "id": f"suggestion-{now.strftime('%Y%m%d%H%M%S')}-{user_id}",
        "game_name": game_name.strip(),
        "suggested_by": user_id,
        "created_at": now.isoformat(),
        "status": "pending",
    }
    catalog["suggestions"].append(suggestion)
    catalog["suggestion_cooldowns"][str(user_id)] = now.isoformat()
    _write_catalog(catalog)
    return suggestion