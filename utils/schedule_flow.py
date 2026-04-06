from datetime import timedelta
import hashlib
import json
from os import path

import discord


def get_previous_monday(dt):
    return dt - timedelta(days=dt.weekday())


def get_number_emojis():
    return ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def get_unavailable_emoji():
    return "❌"


DAY_AVAILABILITY_FILE = "data/day_availability.json"


def _build_scope_hash(guild_id: int, channel_id: int, message_id: int, date_str: str) -> str:
    raw = f"{guild_id}:{channel_id}:{message_id}:{date_str}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _build_custom_id(scope_hash: str) -> str:
    return f"sched:unavail:{scope_hash}"


def _read_day_availability_state() -> dict:
    if not path.exists(DAY_AVAILABILITY_FILE):
        return {}
    with open(DAY_AVAILABILITY_FILE, "r") as handle:
        return json.load(handle)


def _write_day_availability_state(data: dict) -> None:
    with open(DAY_AVAILABILITY_FILE, "w") as handle:
        json.dump(data, handle, indent=4)


def _save_day_entry(
    message_id: int,
    guild_id: int,
    channel_id: int,
    date_str: str,
    scope_hash: str,
    button_custom_id: str,
    unavailable_user_ids: set[int],
) -> None:
    data = _read_day_availability_state()
    data[str(message_id)] = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "date_str": date_str,
        "scope_hash": scope_hash,
        "button_custom_id": button_custom_id,
        "unavailable_user_ids": sorted(str(uid) for uid in unavailable_user_ids),
    }
    _write_day_availability_state(data)


def _load_day_entry(message_id: int) -> dict | None:
    data = _read_day_availability_state()
    return data.get(str(message_id))


def build_day_status_message(date_str: str, unavailable_user_ids: set[int]) -> str:
    if not unavailable_user_ids:
        unavailable_text = "No one marked unavailable all day yet."
    else:
        mentions = ", ".join(f"<@{uid}>" for uid in sorted(unavailable_user_ids))
        unavailable_text = mentions
    return (
        f"**{date_str}**\n"
        f"❌ **Unavailable All Day:** {unavailable_text}\n"
        "-# Use reactions for time slots, or use the button below for all-day unavailable."
    )


class DailyAvailabilityView(discord.ui.View):
    def __init__(
        self,
        date_str: str,
        guild_id: int,
        channel_id: int,
        message_id: int | None = None,
        scope_hash: str | None = None,
        button_custom_id: str | None = None,
        unavailable_user_ids: set[int] | None = None,
    ):
        super().__init__(timeout=None)  # persistent view
        self.date_str = date_str
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        message_for_hash = message_id or 0
        self.scope_hash = scope_hash or _build_scope_hash(guild_id, channel_id, message_for_hash, date_str)
        self.button_custom_id = button_custom_id or _build_custom_id(self.scope_hash)
        self.unavailable_user_ids: set[int] = unavailable_user_ids or set()

        self.toggle_button = discord.ui.Button(
            label="Toggle Unavailable All Day",
            style=discord.ButtonStyle.secondary,
            emoji="❌",
            custom_id=self.button_custom_id,
        )
        self.toggle_button.callback = self.toggle_unavailable
        self.add_item(self.toggle_button)

    def bind_message(self, message_id: int) -> None:
        self.message_id = message_id
        self.scope_hash = _build_scope_hash(self.guild_id, self.channel_id, message_id, self.date_str)
        self.button_custom_id = _build_custom_id(self.scope_hash)
        self.toggle_button.custom_id = self.button_custom_id
        _save_day_entry(
            message_id=message_id,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            date_str=self.date_str,
            scope_hash=self.scope_hash,
            button_custom_id=self.button_custom_id,
            unavailable_user_ids=self.unavailable_user_ids,
        )

    async def toggle_unavailable(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.unavailable_user_ids:
            self.unavailable_user_ids.remove(user_id)
            status = "Removed your all-day unavailable status for this day."
        else:
            self.unavailable_user_ids.add(user_id)
            status = "Marked you as unavailable all day for this day."

        await interaction.response.edit_message(
            content=build_day_status_message(self.date_str, self.unavailable_user_ids),
            view=self,
        )

        if interaction.message and interaction.message.id:
            self.message_id = interaction.message.id

        if self.message_id is not None:
            _save_day_entry(
                message_id=self.message_id,
                guild_id=self.guild_id,
                channel_id=self.channel_id,
                date_str=self.date_str,
                scope_hash=self.scope_hash,
                button_custom_id=self.button_custom_id,
                unavailable_user_ids=self.unavailable_user_ids,
            )

        await interaction.followup.send(f"✅ {status}", ephemeral=True)


def register_persistent_daily_views(bot) -> int:
    """Re-register persistent day availability views after bot restart."""
    data = _read_day_availability_state()
    registered = 0

    for message_id_text, entry in data.items():
        try:
            message_id = int(message_id_text)
            guild_id = int(entry.get("guild_id", "0"))
            channel_id = int(entry.get("channel_id", "0"))
            date_str = entry.get("date_str", "Unknown Day")
            scope_hash = entry.get("scope_hash")
            button_custom_id = entry.get("button_custom_id")
            unavailable_user_ids = {
                int(uid) for uid in entry.get("unavailable_user_ids", []) if str(uid).isdigit()
            }

            if guild_id == 0 or channel_id == 0:
                continue

            view = DailyAvailabilityView(
                date_str=date_str,
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
                scope_hash=scope_hash,
                button_custom_id=button_custom_id,
                unavailable_user_ids=unavailable_user_ids,
            )
            bot.add_view(view, message_id=message_id)
            registered += 1
        except Exception:
            continue

    return registered


class WeeklyScheduleIntroView(discord.ui.LayoutView):
    def __init__(self, team_role_mention: str, start_date):
        super().__init__(timeout=60)
        number_emojis = get_number_emojis()
        unavailable_emoji = get_unavailable_emoji()
        time_labels = [
            "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM",
            "7 PM", "8 PM", "9 PM", "10 PM",
        ]
        times_str = "\n".join([f"{emoji} = {label}" for emoji, label in zip(number_emojis, time_labels)])
        times_str += f"\n{unavailable_emoji} = Not Available (all day)"

        container = discord.ui.Container(accent_color=discord.Color.blue())
        container.add_item(discord.ui.TextDisplay("## Weekly Scheduling"))
        container.add_item(
            discord.ui.TextDisplay(
                (
                    f"{team_role_mention}\n"
                    f"**{start_date.strftime('%A: The %d of %B')}**\n\n"
                    "Scheduling for this week!\n"
                    "Each day will have a message for you to react to.\n"
                    "Time slots run from **1 PM to 10 PM**.\n"
                    f"React with the emojis below:\n\n{times_str}"
                )
            )
        )
        container.add_item(discord.ui.TextDisplay("-# React to each day to indicate your availability."))
        self.add_item(container)


async def send_weekly_schedule_messages(channel, team_role_mention, start_date):
    await channel.send(view=WeeklyScheduleIntroView(team_role_mention, start_date))

    number_emojis = get_number_emojis()
    unavailable_emoji = get_unavailable_emoji()
    guild_id = int(channel.guild.id)
    channel_id = int(channel.id)
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        day_str = day_date.strftime("%A: The %d of %B")
        view = DailyAvailabilityView(day_str, guild_id=guild_id, channel_id=channel_id)
        msg_content = build_day_status_message(day_str, view.unavailable_user_ids)
        message = await channel.send(msg_content, view=view)
        view.bind_message(message.id)
        for emoji in number_emojis:
            await message.add_reaction(emoji)
        await message.add_reaction(unavailable_emoji)
