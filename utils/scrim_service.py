import base64
import json
from datetime import datetime, timezone
from os import makedirs, path
from uuid import uuid4


SCRIM_EVENTS_DIR = "data/scrim_requests"


def _requests_file(guild_id: str) -> str:
    makedirs(SCRIM_EVENTS_DIR, exist_ok=True)
    return path.join(SCRIM_EVENTS_DIR, f"{guild_id}.json")


def _load_requests(guild_id: str) -> dict:
    file_path = _requests_file(guild_id)
    if not path.exists(file_path):
        return {}
    with open(file_path, "r") as handle:
        return json.load(handle)


def _save_requests(guild_id: str, requests: dict) -> None:
    with open(_requests_file(guild_id), "w") as handle:
        json.dump(requests, handle, indent=4)


def make_scrim_event_id(requesting_team: str, target_team: str, game_id: str) -> str:
    payload = {
        "requesting_team": requesting_team,
        "target_team": target_team,
        "game_id": game_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "nonce": uuid4().hex,
    }
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"scrim_{encoded}"


def save_scrim_request(guild_id: str, request: dict) -> None:
    requests = _load_requests(guild_id)
    requests[request["event_id"]] = request
    _save_requests(guild_id, requests)


def get_scrim_request(guild_id: str, event_id: str) -> dict | None:
    return _load_requests(guild_id).get(event_id)


def update_scrim_request(guild_id: str, event_id: str, **changes) -> dict | None:
    requests = _load_requests(guild_id)
    request = requests.get(event_id)
    if request is None:
        return None
    request.update(changes)
    requests[event_id] = request
    _save_requests(guild_id, requests)
    return request