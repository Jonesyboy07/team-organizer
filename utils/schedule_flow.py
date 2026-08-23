import json
import secrets
from datetime import timedelta
from os import makedirs, path

import discord

AVAILABLE_ALL_DAY_EMOJI = "✅"
UNAVAILABLE_ALL_DAY_EMOJI = "❌"

SCHEDULE_EVENTS_DIR = "data/schedule_events"


def get_previous_monday(dt):
    return dt - timedelta(days=dt.weekday())


def get_number_emojis():
    return ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def get_unavailable_emoji():
    return UNAVAILABLE_ALL_DAY_EMOJI


def generate_event_id() -> str:
    """6-char hex ID, unique per-guild but may repeat across servers."""
    return secrets.token_hex(3)


def _events_file(guild_id) -> str:
    makedirs(SCHEDULE_EVENTS_DIR, exist_ok=True)
    return path.join(SCHEDULE_EVENTS_DIR, f"{guild_id}.json")


def _load_guild_events(guild_id) -> dict:
    file_path = _events_file(guild_id)
    if not path.exists(file_path):
        return {}
    with open(file_path, "r") as handle:
        return json.load(handle)


def _save_guild_events(guild_id, events: dict) -> None:
    with open(_events_file(guild_id), "w") as handle:
        json.dump(events, handle, indent=4)


def get_schedule_event(guild_id, event_id: str) -> dict | None:
    return _load_guild_events(guild_id).get(event_id)


def list_schedule_events(guild_id) -> dict:
    return _load_guild_events(guild_id)


def build_weekly_intro_message(team_role_mention: str, start_date, event_id: str) -> str:
    number_emojis = get_number_emojis()
    time_labels = [
        "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM",
        "7 PM", "8 PM", "9 PM", "10 PM",
    ]
    times_str = "\n".join([f"{emoji} = {label}" for emoji, label in zip(number_emojis, time_labels)])

    return (
        "## Weekly Scheduling\n"
        f"{team_role_mention}\n"
        f"**{start_date.strftime('%A: The %d of %B')}**\n\n"
        "React to each day below with the time slots you're available for.\n\n"
        f"{times_str}\n"
        f"{AVAILABLE_ALL_DAY_EMOJI} = Available all day, {UNAVAILABLE_ALL_DAY_EMOJI} = Unavailable all day\n"
        f"-# Event ID: `{event_id}`"
    )


async def send_weekly_schedule_messages(channel, team_role_mention, start_date, team: dict):
    guild_id = str(channel.guild.id)
    event_id = generate_event_id()

    await channel.send(build_weekly_intro_message(team_role_mention, start_date, event_id))

    number_emojis = get_number_emojis()
    days = {}
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        date_key = day_date.strftime("%Y-%m-%d")
        day_str = day_date.strftime("%A: The %d of %B")
        message = await channel.send(f"## {day_str}\n-# Event ID: `{event_id}`")
        for emoji in number_emojis:
            await message.add_reaction(emoji)
        await message.add_reaction(AVAILABLE_ALL_DAY_EMOJI)
        await message.add_reaction(UNAVAILABLE_ALL_DAY_EMOJI)
        days[date_key] = message.id

    events = _load_guild_events(guild_id)
    events[event_id] = {
        "team_name": team.get("team_name"),
        "team_role_id": team.get("team_role_id"),
        "team_captain_id": team.get("team_captain_id"),
        "channel_id": channel.id,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "days": days,
    }
    _save_guild_events(guild_id, events)

    return event_id


async def fetch_day_availability(channel, message_id) -> tuple[set[int], set[int], set[int]]:
    """Return (available_all_day_ids, unavailable_all_day_ids, partial_ids) reacted on a day's message."""
    try:
        message = await channel.fetch_message(int(message_id))
    except discord.NotFound:
        return set(), set(), set()

    number_emojis = set(get_number_emojis())
    available_ids, unavailable_ids, partial_ids = set(), set(), set()

    for reaction in message.reactions:
        emoji_str = str(reaction.emoji)
        if emoji_str == AVAILABLE_ALL_DAY_EMOJI:
            target = available_ids
        elif emoji_str == UNAVAILABLE_ALL_DAY_EMOJI:
            target = unavailable_ids
        elif emoji_str in number_emojis:
            target = partial_ids
        else:
            continue

        async for user in reaction.users():
            if not user.bot:
                target.add(user.id)

    return available_ids, unavailable_ids, partial_ids

