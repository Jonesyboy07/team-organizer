import discord

from utils.funcs import log_to_discord
from utils.command_helpers import CommandResponse

ATTEND_EMOJI = "✅"
MAYBE_EMOJI = "🤔"
CANT_EMOJI = "❌"


def ensure_event_lists(event_data: dict):
    for key in ["attend", "maybe", "cant"]:
        event_data.setdefault(key, [])


def _mention_list(user_ids):
    return "\\n".join(f"<@{uid}>" for uid in user_ids) if user_ids else "No one yet"


class EventActionsRow(discord.ui.ActionRow):
    def __init__(self, parent_view: "EventRSVPLayoutView"):
        super().__init__()
        self.parent_view = parent_view

    @discord.ui.button(label="Can Attend", style=discord.ButtonStyle.success, emoji=ATTEND_EMOJI)
    async def can_attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.parent_view.handle_rsvp(interaction, "attend", "Can Attend")

    @discord.ui.button(label="May be able to", style=discord.ButtonStyle.secondary, emoji=MAYBE_EMOJI)
    async def maybe_attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.parent_view.handle_rsvp(interaction, "maybe", "May be able to")

    @discord.ui.button(label="Can't Attend", style=discord.ButtonStyle.danger, emoji=CANT_EMOJI)
    async def cant_attend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.parent_view.handle_rsvp(interaction, "cant", "Can't Attend")

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.secondary, emoji="🚫")
    async def remove_attendance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.parent_view.handle_remove_attendance(interaction)


class EventRSVPLayoutView(discord.ui.LayoutView):
    def __init__(self, event_cog, guild_id: str, message_id: int, event_data: dict, team_role_mention: str, unix_time: int, tz_name: str):
        super().__init__(timeout=None)
        self.event_cog = event_cog
        self.guild_id = guild_id
        self.message_id = message_id

        self.header = discord.ui.TextDisplay(f"## {event_data.get('event_name', 'Event')}")
        self.meta = discord.ui.TextDisplay(
            f"{team_role_mention}\\n"
            f"**Event Time:** <t:{unix_time}:F> ({tz_name})\\n"
            f"**Relative:** <t:{unix_time}:R>\\n"
            "Use the buttons below to RSVP."
        )
        self.attendance = discord.ui.TextDisplay("")

        self.actions = EventActionsRow(self)

        container = discord.ui.Container(accent_color=discord.Color.purple())
        container.add_item(self.header)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, divider=True))
        container.add_item(self.meta)
        container.add_item(self.attendance)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large, divider=False))
        container.add_item(self.actions)
        self.add_item(container)

        self.refresh_content(event_data)

    def refresh_content(self, event_data: dict):
        ensure_event_lists(event_data)
        attend = event_data.get("attend", [])
        maybe = event_data.get("maybe", [])
        cant = event_data.get("cant", [])
        self.attendance.content = (
            f"### Can Attend {ATTEND_EMOJI} ({len(attend)})\\n{_mention_list(attend)}\\n\\n"
            f"### May be able to {MAYBE_EMOJI} ({len(maybe)})\\n{_mention_list(maybe)}\\n\\n"
            f"### Can't Attend {CANT_EMOJI} ({len(cant)})\\n{_mention_list(cant)}"
        )

    async def handle_rsvp(self, interaction: discord.Interaction, status_key: str, label: str):
        events = self.event_cog.load_events(self.guild_id)
        event_data = events.get(str(self.message_id))
        if not event_data:
            await CommandResponse.error(interaction, "This event is no longer available.")
            return

        ensure_event_lists(event_data)
        user_id = interaction.user.id
        for key in ["attend", "maybe", "cant"]:
            if user_id in event_data[key]:
                event_data[key].remove(user_id)
        event_data[status_key].append(user_id)

        events[str(self.message_id)] = event_data
        self.event_cog.save_events(self.guild_id, events)
        self.refresh_content(event_data)

        await interaction.response.edit_message(view=self)
        await CommandResponse.followup_success(interaction, f"You've RSVP'd as **{label}**.")

        await log_to_discord(
            self.event_cog.bot,
            self.guild_id,
            f"{interaction.user} ({interaction.user.id}) RSVP '{label}' for event {event_data.get('event_name', '')}",
        )

    async def handle_remove_attendance(self, interaction: discord.Interaction):
        events = self.event_cog.load_events(self.guild_id)
        event_data = events.get(str(self.message_id))
        if not event_data:
            await CommandResponse.error(interaction, "This event is no longer available.")
            return

        ensure_event_lists(event_data)
        removed = False
        user_id = interaction.user.id
        for key in ["attend", "maybe", "cant"]:
            if user_id in event_data[key]:
                event_data[key].remove(user_id)
                removed = True

        events[str(self.message_id)] = event_data
        self.event_cog.save_events(self.guild_id, events)
        self.refresh_content(event_data)

        await interaction.response.edit_message(view=self)
        if removed:
            await CommandResponse.followup_success(interaction, "Your attendance has been removed.")
            await log_to_discord(
                self.event_cog.bot,
                self.guild_id,
                f"{interaction.user} ({interaction.user.id}) removed attendance for event {event_data.get('event_name', '')}",
            )
        else:
            await CommandResponse.followup_info(interaction, "You were not signed up for this event.")
