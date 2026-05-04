from datetime import timedelta
import hashlib
import json
from os import path

import discord


AVAILABLE_ALL_DAY_EMOJI = "✅"
UNAVAILABLE_ALL_DAY_EMOJI = "🚫"


def get_previous_monday(dt):
    return dt - timedelta(days=dt.weekday())


def get_number_emojis():
    return ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def get_unavailable_emoji():
    return UNAVAILABLE_ALL_DAY_EMOJI


DAY_AVAILABILITY_FILE = "data/day_availability.json"


def _build_scope_hash(guild_id: int, channel_id: int, message_id: int, date_str: str) -> str:
    raw = f"{guild_id}:{channel_id}:{message_id}:{date_str}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _build_custom_id(scope_hash: str, button_type: str = "unavail") -> str:
    return f"sched:{button_type}:{scope_hash}"


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
    available_all_day_user_ids: set[int] | None = None,
) -> None:
    data = _read_day_availability_state()
    data[str(message_id)] = {
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "date_str": date_str,
        "scope_hash": scope_hash,
        "button_custom_id": button_custom_id,
        "unavailable_user_ids": sorted(str(uid) for uid in unavailable_user_ids),
        "available_all_day_user_ids": sorted(str(uid) for uid in (available_all_day_user_ids or set())),
    }
    _write_day_availability_state(data)


def _load_day_entry(message_id: int) -> dict | None:
    data = _read_day_availability_state()
    return data.get(str(message_id))


def _format_user_mentions(user_ids: set[int], empty_text: str) -> str:
    if not user_ids:
        return empty_text
    return ", ".join(f"<@{uid}>" for uid in sorted(user_ids))


def build_day_status_summary(
    unavailable_user_ids: set[int],
    available_all_day_user_ids: set[int] | None = None,
) -> str:
    if available_all_day_user_ids is None:
        available_all_day_user_ids = set()

    available_text = _format_user_mentions(
        available_all_day_user_ids,
        "No one marked available all day yet.",
    )
    unavailable_text = _format_user_mentions(
        unavailable_user_ids,
        "No one marked unavailable all day yet.",
    )

    return (
        f"### {AVAILABLE_ALL_DAY_EMOJI} Available All Day ({len(available_all_day_user_ids)})\n"
        f"{available_text}\n\n"
        f"### {UNAVAILABLE_ALL_DAY_EMOJI} Unavailable All Day ({len(unavailable_user_ids)})\n"
        f"{unavailable_text}"
    )


class DailyAvailabilityView(discord.ui.LayoutView):
    def __init__(
        self,
        date_str: str,
        guild_id: int,
        channel_id: int,
        message_id: int | None = None,
        scope_hash: str | None = None,
        button_custom_id: str | None = None,
        unavailable_user_ids: set[int] | None = None,
        available_all_day_user_ids: set[int] | None = None,
    ):
        super().__init__(timeout=None)  # persistent view
        self.date_str = date_str
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        message_for_hash = message_id or 0
        self.scope_hash = scope_hash or _build_scope_hash(guild_id, channel_id, message_for_hash, date_str)
        self.unavailable_button_custom_id = button_custom_id or _build_custom_id(self.scope_hash, "unavail")
        self.available_button_custom_id = _build_custom_id(self.scope_hash, "avail")
        self.unavailable_user_ids: set[int] = unavailable_user_ids or set()
        self.available_all_day_user_ids: set[int] = available_all_day_user_ids or set()

        self.header = discord.ui.TextDisplay(f"## {self.date_str}")
        self.status_display = discord.ui.TextDisplay("")
        self.guidance = discord.ui.TextDisplay(
            "-# Use 1-10 reactions for time slots. Use the buttons below for full-day availability."
        )

        container = discord.ui.Container(accent_color=discord.Color.blurple())
        container.add_item(self.header)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(self.status_display)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(self.guidance)
        self.add_item(container)

        self.toggle_available_button = discord.ui.Button(
            label="Available All Day",
            style=discord.ButtonStyle.success,
            emoji=AVAILABLE_ALL_DAY_EMOJI,
            custom_id=self.available_button_custom_id,
        )
        self.toggle_available_button.callback = self.toggle_available_all_day
        self.add_item(self.toggle_available_button)

        self.toggle_unavailable_button = discord.ui.Button(
            label="Unavailable All Day",
            style=discord.ButtonStyle.danger,
            emoji=UNAVAILABLE_ALL_DAY_EMOJI,
            custom_id=self.unavailable_button_custom_id,
        )
        self.toggle_unavailable_button.callback = self.toggle_unavailable
        self.add_item(self.toggle_unavailable_button)

        self.refresh_content()

    def refresh_content(self) -> None:
        self.status_display.content = build_day_status_summary(
            self.unavailable_user_ids,
            self.available_all_day_user_ids,
        )
        self.toggle_available_button.label = f"Available All Day ({len(self.available_all_day_user_ids)})"
        self.toggle_unavailable_button.label = f"Unavailable All Day ({len(self.unavailable_user_ids)})"

    def _persist_if_bound(self) -> None:
        if self.message_id is None:
            return

        _save_day_entry(
            message_id=self.message_id,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            date_str=self.date_str,
            scope_hash=self.scope_hash,
            button_custom_id=self.unavailable_button_custom_id,
            unavailable_user_ids=self.unavailable_user_ids,
            available_all_day_user_ids=self.available_all_day_user_ids,
        )

    def bind_message(self, message_id: int) -> None:
        self.message_id = message_id
        self.scope_hash = _build_scope_hash(self.guild_id, self.channel_id, message_id, self.date_str)
        self.unavailable_button_custom_id = _build_custom_id(self.scope_hash, "unavail")
        self.available_button_custom_id = _build_custom_id(self.scope_hash, "avail")
        self.toggle_unavailable_button.custom_id = self.unavailable_button_custom_id
        self.toggle_available_button.custom_id = self.available_button_custom_id
        _save_day_entry(
            message_id=message_id,
            guild_id=self.guild_id,
            channel_id=self.channel_id,
            date_str=self.date_str,
            scope_hash=self.scope_hash,
            button_custom_id=self.unavailable_button_custom_id,
            unavailable_user_ids=self.unavailable_user_ids,
            available_all_day_user_ids=self.available_all_day_user_ids,
        )

    async def toggle_unavailable(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.unavailable_user_ids:
            self.unavailable_user_ids.remove(user_id)
            status = "Removed your all-day unavailable status for this day."
        else:
            self.unavailable_user_ids.add(user_id)
            removed_available = user_id in self.available_all_day_user_ids
            self.available_all_day_user_ids.discard(user_id)
            status = "Marked you as unavailable all day for this day."
            if removed_available:
                status += " Removed your available all day status."

        self.refresh_content()

        await interaction.response.edit_message(view=self)

        if interaction.message and interaction.message.id:
            self.message_id = interaction.message.id

        self._persist_if_bound()

        await interaction.followup.send(f"✅ {status}", ephemeral=True)

    async def toggle_available_all_day(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in self.available_all_day_user_ids:
            self.available_all_day_user_ids.remove(user_id)
            status = "Removed your available all day status."
        else:
            self.available_all_day_user_ids.add(user_id)
            removed_unavailable = user_id in self.unavailable_user_ids
            self.unavailable_user_ids.discard(user_id)
            status = "Marked you as available all day."
            if removed_unavailable:
                status += " Removed your unavailable all day status."

        self.refresh_content()

        await interaction.response.edit_message(view=self)

        if interaction.message and interaction.message.id:
            self.message_id = interaction.message.id

        self._persist_if_bound()

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
            available_all_day_raw = entry.get(
                "available_all_day_user_ids",
                entry.get("available_all_week_user_ids", []),
            )
            available_all_day_user_ids = {
                int(uid) for uid in available_all_day_raw if str(uid).isdigit()
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
                available_all_day_user_ids=available_all_day_user_ids,
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
        time_labels = [
            "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM",
            "7 PM", "8 PM", "9 PM", "10 PM",
        ]
        times_str = "\n".join([f"{emoji} = {label}" for emoji, label in zip(number_emojis, time_labels)])
        times_str += (
            f"\n{AVAILABLE_ALL_DAY_EMOJI} button = Available All Day"
            f"\n{UNAVAILABLE_ALL_DAY_EMOJI} button = Unavailable All Day"
        )

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
                    f"Use the reactions below for time slots, then use the day card buttons for all-day status:\n\n{times_str}"
                )
            )
        )
        container.add_item(discord.ui.TextDisplay("-# React to each day to indicate your availability."))
        self.add_item(container)


async def send_weekly_schedule_messages(channel, team_role_mention, start_date):
    await channel.send(view=WeeklyScheduleIntroView(team_role_mention, start_date))

    number_emojis = get_number_emojis()
    guild_id = int(channel.guild.id)
    channel_id = int(channel.id)
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        day_str = day_date.strftime("%A: The %d of %B")
        view = DailyAvailabilityView(day_str, guild_id=guild_id, channel_id=channel_id)
        message = await channel.send(view=view)
        view.bind_message(message.id)
        for emoji in number_emojis:
            await message.add_reaction(emoji)
