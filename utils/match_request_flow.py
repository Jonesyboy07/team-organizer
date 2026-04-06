from datetime import datetime
import uuid

import discord
import pytz

from utils.constants import MAJOR_TIMEZONES, TIMEZONE_MAP
from utils.funcs import CheckIfAdminRole, log_to_discord
from utils.team_service import find_team_by_name


TIME_OPTIONS = [
    ("13:00", "1:00 PM"),
    ("14:00", "2:00 PM"),
    ("15:00", "3:00 PM"),
    ("16:00", "4:00 PM"),
    ("17:00", "5:00 PM"),
    ("18:00", "6:00 PM"),
    ("19:00", "7:00 PM"),
    ("20:00", "8:00 PM"),
    ("21:00", "9:00 PM"),
    ("22:00", "10:00 PM"),
]


def parse_request_datetime(date_text: str, time_text: str, timezone_label: str):
    tz_name = TIMEZONE_MAP.get(timezone_label, timezone_label)
    timezone = pytz.timezone(tz_name)
    naive_dt = datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M")
    aware_dt = timezone.localize(naive_dt)
    return aware_dt


class RequestTimezoneSelect(discord.ui.Select):
    def __init__(self, parent_view: "MatchRequestSetupView"):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=tz, value=tz) for tz in MAJOR_TIMEZONES[:25]]
        super().__init__(
            placeholder="Select timezone...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_timezone = self.values[0]
        await interaction.response.defer()


class RequestTimeSelect(discord.ui.Select):
    def __init__(self, parent_view: "MatchRequestSetupView"):
        self.parent_view = parent_view
        options = [discord.SelectOption(label=label, value=value) for value, label in TIME_OPTIONS]
        super().__init__(
            placeholder="Select time...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_time = self.values[0]
        await interaction.response.defer()


class MatchRequestSetupView(discord.ui.View):
    def __init__(
        self,
        bot,
        guild_id: str,
        requester: discord.abc.User,
        requesting_team_name: str,
        target_team_name: str,
        target_team_captain_id: int,
        request_channel: discord.TextChannel,
        request_date: str,
        notes: str,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.requester = requester
        self.requesting_team_name = requesting_team_name
        self.target_team_name = target_team_name
        self.target_team_captain_id = target_team_captain_id
        self.request_channel = request_channel
        self.request_date = request_date
        self.notes = notes
        self.selected_timezone = None
        self.selected_time = None

        self.add_item(RequestTimezoneSelect(self))
        self.add_item(RequestTimeSelect(self))

    @discord.ui.button(label="Submit Request", style=discord.ButtonStyle.success)
    async def submit_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message("Only the original requester can submit this request.", ephemeral=True)
            return

        if self.selected_timezone is None or self.selected_time is None:
            await interaction.response.send_message("Please choose both a timezone and time first.", ephemeral=True)
            return

        try:
            dt = parse_request_datetime(self.request_date, self.selected_time, self.selected_timezone)
        except ValueError:
            await interaction.response.send_message(
                "Invalid date format. Please use YYYY-MM-DD when running the command.",
                ephemeral=True,
            )
            return
        except Exception as exc:  # noqa: BLE001
            await log_to_discord(
                self.bot,
                self.guild_id,
                f"request_match datetime parse failure for {self.requester.id}: {repr(exc)}",
            )
            await interaction.response.send_message(
                "I could not parse the selected date/time/timezone. Please try again.",
                ephemeral=True,
            )
            return

        unix_timestamp = int(dt.timestamp())
        request_id = f"req-{uuid.uuid4().hex[:8]}"

        try:
            review_view = MatchRequestReviewView(
                guild_id=self.guild_id,
                request_id=request_id,
                requester_id=self.requester.id,
                requester_display=str(self.requester),
                requesting_team_name=self.requesting_team_name,
                target_team_name=self.target_team_name,
                target_team_captain_id=self.target_team_captain_id,
                request_timestamp=unix_timestamp,
                timezone_label=self.selected_timezone,
                notes=self.notes,
            )
            await self.request_channel.send(view=review_view)
        except Exception as exc:  # noqa: BLE001
            await log_to_discord(
                self.bot,
                self.guild_id,
                f"request_match send failure for {self.requester.id} into {self.request_channel.id}: {repr(exc)}",
            )
            await interaction.response.send_message(
                "I could not send this request to the configured channel. Check permissions and try again.",
                ephemeral=True,
            )
            return

        await log_to_discord(
            self.bot,
            self.guild_id,
            f"Match request {request_id} submitted by {self.requester} ({self.requester.id}) "
            f"from {self.requesting_team_name} to {self.target_team_name} at <t:{unix_timestamp}:F>",
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"Request sent to {self.request_channel.mention} for <t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>).",
            ephemeral=True,
        )


class RequestInfoModal(discord.ui.Modal):
    def __init__(self, parent_view: "MatchRequestReviewView"):
        super().__init__(title="Request Further Info")
        self.parent_view = parent_view
        self.question = discord.ui.TextInput(
            label="What extra info do you need?",
            style=discord.TextStyle.long,
            max_length=500,
            required=True,
        )
        self.add_item(self.question)

    async def on_submit(self, interaction: discord.Interaction):
        if self.parent_view.resolved:
            await interaction.response.send_message("This request has already been resolved.", ephemeral=True)
            return

        if not self.parent_view.can_review(interaction):
            await interaction.response.send_message("You are not allowed to review this request.", ephemeral=True)
            return

        question_text = str(self.question.value)
        dm_message = (
            f"Your match request from **{self.parent_view.requesting_team_name}** to "
            f"**{self.parent_view.target_team_name}** needs more info.\n\n"
            f"Reviewer: {interaction.user.mention}\n"
            f"Question: {question_text}"
        )
        sent, dm_error = await self.parent_view.try_dm_requester(interaction, dm_message, "request_further_info")

        if sent:
            status = "Requested further info and DM sent to requester."
        else:
            status = (
                "Requested further info, but DM could not be delivered. "
                "The requester may have DMs disabled."
            )

        await log_to_discord(
            interaction.client,
            self.parent_view.guild_id,
            f"Further info requested by {interaction.user} ({interaction.user.id}) for request {self.parent_view.request_id}. "
            f"DM delivered={sent}. Error={dm_error}",
        )
        await interaction.response.send_message(status, ephemeral=True)


class MatchRequestActionRow(discord.ui.ActionRow):
    def __init__(self, view: "MatchRequestReviewView"):
        super().__init__()
        self.parent_view = view

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.parent_view.handle_resolution(interaction, approved=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.parent_view.handle_resolution(interaction, approved=False)

    @discord.ui.button(label="Request Further Info", style=discord.ButtonStyle.secondary)
    async def request_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RequestInfoModal(self.parent_view))


class MatchRequestReviewView(discord.ui.LayoutView):
    def __init__(
        self,
        guild_id: str,
        request_id: str,
        requester_id: int,
        requester_display: str,
        requesting_team_name: str,
        target_team_name: str,
        target_team_captain_id: int,
        request_timestamp: int,
        timezone_label: str,
        notes: str,
    ):
        super().__init__(timeout=604800)
        self.guild_id = guild_id
        self.request_id = request_id
        self.requester_id = requester_id
        self.requester_display = requester_display
        self.requesting_team_name = requesting_team_name
        self.target_team_name = target_team_name
        self.target_team_captain_id = target_team_captain_id
        self.request_timestamp = request_timestamp
        self.timezone_label = timezone_label
        self.notes = notes or "No additional notes."
        self.resolved = False

        self.header = discord.ui.TextDisplay("## Match Request")
        self.status = discord.ui.TextDisplay("-# Status: Pending review")
        details = discord.ui.TextDisplay(
            f"**Request ID:** `{self.request_id}`\n"
            f"**Requester:** <@{self.requester_id}> ({self.requester_display})\n"
            f"**Teams:** {self.requesting_team_name} -> {self.target_team_name}\n"
            f"**Requested Time:** <t:{self.request_timestamp}:F> (<t:{self.request_timestamp}:R>)\n"
            f"**Timezone Selected:** {self.timezone_label}\n"
            f"**Notes:** {self.notes}"
        )

        self.actions = MatchRequestActionRow(self)

        container = discord.ui.Container(accent_color=discord.Color.blurple())
        container.add_item(self.header)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, divider=True))
        container.add_item(self.status)
        container.add_item(details)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large, divider=False))
        container.add_item(self.actions)

        self.add_item(container)

    def can_review(self, interaction: discord.Interaction):
        if interaction.guild is None:
            return False

        user_role_ids = [role.id for role in interaction.user.roles]
        return CheckIfAdminRole(user_role_ids, self.guild_id) or interaction.user.id == int(self.target_team_captain_id)

    async def try_dm_requester(self, interaction: discord.Interaction, message: str, reason: str):
        dm_error = None
        try:
            user = interaction.client.get_user(self.requester_id)
            if user is None:
                user = await interaction.client.fetch_user(self.requester_id)
            await user.send(message)
            return True, None
        except Exception as exc:  # noqa: BLE001
            dm_error = repr(exc)
            await log_to_discord(
                interaction.client,
                self.guild_id,
                f"DM failed ({reason}) for requester {self.requester_id}. Error: {dm_error}",
            )
            return False, dm_error

    def disable_actions(self):
        for child in self.actions.children:
            child.disabled = True

    async def handle_resolution(self, interaction: discord.Interaction, approved: bool):
        if self.resolved:
            await interaction.response.send_message("This request has already been resolved.", ephemeral=True)
            return

        if not self.can_review(interaction):
            await interaction.response.send_message("You are not allowed to review this request.", ephemeral=True)
            return

        decision = "accepted" if approved else "denied"
        self.resolved = True
        self.status.content = f"-# Status: {decision.title()} by {interaction.user.display_name}"
        self.disable_actions()

        dm_message = (
            f"Your match request (**{self.requesting_team_name} -> {self.target_team_name}**) "
            f"for <t:{self.request_timestamp}:F> was **{decision}** by {interaction.user.mention}."
        )
        sent, dm_error = await self.try_dm_requester(interaction, dm_message, f"request_{decision}")

        await log_to_discord(
            interaction.client,
            self.guild_id,
            f"Match request {self.request_id} {decision} by {interaction.user} ({interaction.user.id}). "
            f"DM delivered={sent}. Error={dm_error}",
        )

        await interaction.response.edit_message(view=self)
        if sent:
            await interaction.followup.send(f"Request {decision}. The requester was notified by DM.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Request {decision}, but DM could not be delivered to the requester. They may have DMs disabled.",
                ephemeral=True,
            )
