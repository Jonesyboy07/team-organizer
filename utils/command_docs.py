import json
from os import path

import discord
from discord import app_commands


SECTION_ORDER = ["Setup", "General", "Teams", "Scheduling", "Event"]

COMMAND_SECTION = {
    "setup": "Setup",
    "addbotchannel": "Setup",
    "removebotchannel": "Setup",
    "addadminrole": "Setup",
    "removeadminrole": "Setup",
    "listbotchannels": "Setup",
    "listadminroles": "Setup",
    "setbotlogchannel": "Setup",
    "help": "General",
    "quickstart": "General",
    "info": "General",
    "invite": "General",
    "version": "General",
    "ping": "General",
    "stats": "General",
    "my_teams": "Teams",
    "create_team": "Teams",
    "list_teams": "Teams",
    "delete_team": "Teams",
    "modify_team": "Teams",
    "request_match": "Teams",
    "send_schedule": "Scheduling",
    "event": "Event",
}


TYPE_LABELS = {
    discord.AppCommandOptionType.string: "text",
    discord.AppCommandOptionType.integer: "number",
    discord.AppCommandOptionType.number: "number",
    discord.AppCommandOptionType.boolean: "true|false",
    discord.AppCommandOptionType.user: "member",
    discord.AppCommandOptionType.role: "role",
    discord.AppCommandOptionType.channel: "channel",
    discord.AppCommandOptionType.mentionable: "mention",
    discord.AppCommandOptionType.attachment: "file",
}


def _load_existing_commands_map(file_path: str):
    """Load existing command entries to preserve admin_required values and ordering."""
    if not path.exists(file_path):
        return {}, {}

    with open(file_path, "r") as handle:
        data = json.load(handle)

    existing_admin = {}
    order = {}
    idx = 0
    for section in data.get("sections", []):
        for cmd in section.get("commands", []):
            name = cmd.get("name")
            if not name:
                continue
            existing_admin[name] = bool(cmd.get("admin_required", False))
            order[name] = idx
            idx += 1

    return existing_admin, order


def _build_usage(command: app_commands.Command) -> str:
    parts = [f"/{command.name}"]
    for param in command.parameters:
        type_label = TYPE_LABELS.get(param.type, "value")
        token = f"{param.display_name}:<{type_label}>"
        if param.required:
            parts.append(token)
        else:
            parts.append(f"[{token}]")
    return " ".join(parts)


def _is_slash_command(cmd) -> bool:
    return isinstance(cmd, app_commands.Command) and getattr(cmd, "parent", None) is None


def sync_commands_json(bot, file_path: str = "data/commands.json") -> int:
    """Build data/commands.json from currently loaded slash commands."""
    existing_admin, existing_order = _load_existing_commands_map(file_path)

    commands_by_section = {section: [] for section in SECTION_ORDER}
    discovered = []

    for cmd in bot.tree.get_commands():
        if not _is_slash_command(cmd):
            continue

        section = COMMAND_SECTION.get(cmd.name, "General")
        if section not in commands_by_section:
            commands_by_section[section] = []

        entry = {
            "name": cmd.name,
            "description": cmd.description or "No description provided.",
            "usage": _build_usage(cmd),
            "admin_required": existing_admin.get(cmd.name, False),
        }
        commands_by_section[section].append(entry)
        discovered.append(cmd.name)

    for section_name, entries in commands_by_section.items():
        entries.sort(key=lambda e: (existing_order.get(e["name"], 10_000), e["name"]))

    output_sections = []
    for section in SECTION_ORDER:
        items = commands_by_section.get(section, [])
        if items:
            output_sections.append({"name": section, "commands": items})

    for section_name, entries in commands_by_section.items():
        if section_name not in SECTION_ORDER and entries:
            output_sections.append({"name": section_name, "commands": entries})

    with open(file_path, "w") as handle:
        json.dump({"sections": output_sections}, handle, indent=4)

    return len(discovered)