import json
from os import path

SERVERS_FILE = "data/servers.json"


def _normalize_guild_id(guild_id) -> str:
    return str(guild_id)


def read_servers() -> dict:
    if not path.exists(SERVERS_FILE):
        return {}
    with open(SERVERS_FILE, "r") as handle:
        return json.load(handle)


def write_servers(data: dict, indent: int = 4) -> None:
    with open(SERVERS_FILE, "w") as handle:
        json.dump(data, handle, indent=indent)


def get_server(guild_id) -> dict:
    data = read_servers()
    return data.get(_normalize_guild_id(guild_id), {})


def set_server(guild_id, server_data: dict) -> None:
    gid = _normalize_guild_id(guild_id)
    data = read_servers()
    data[gid] = server_data
    write_servers(data)


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
