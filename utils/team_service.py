import pytz

from discord import app_commands

from utils.constants import TIMEZONE_MAP
from utils.server_store import get_teams


def find_team_by_name(teams, team_name: str):
    lowered = team_name.strip().lower()
    for team in teams:
        if team.get("team_name", "").strip().lower() == lowered:
            return team
    return None


def resolve_team_timezone(team: dict):
    tz_label = team.get("timezone", "UTC")
    tz_name = TIMEZONE_MAP.get(tz_label, tz_label)
    try:
        return pytz.timezone(tz_name)
    except Exception:
        return pytz.UTC


def build_team_name_choices(guild_id, current: str):
    teams = get_teams(guild_id)
    lowered = current.lower()
    return [
        app_commands.Choice(name=t.get("team_name", "Unknown"), value=t.get("team_name", "Unknown"))
        for t in teams
        if lowered in t.get("team_name", "").lower()
    ][:25]
