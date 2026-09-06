from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.command_helpers import CommandResponse
from utils.event_flow import EventRSVPLayoutView
from utils.game_service import get_game, get_games, get_region_name
from utils.scrim_service import get_scrim_request, make_scrim_event_id, save_scrim_request, update_scrim_request
from utils.server_store import get_teams
from utils.team_service import build_team_name_choices, find_team_by_name, resolve_team_timezone


def _request_text(request: dict) -> str:
    return (
        "## Scrim Request\n"
        f"**Requesting Team:** {request['requesting_team_name']}\n"
        f"**Requesting Region:** {request['requesting_region_name']}\n"
        f"**Receiving Team:** {request['target_team_name']}\n"
        f"**Receiving Region:** {request['target_region_name']}\n"
        f"**Game:** {request['game_name']}\n"
        f"**Requested Time:** <t:{request['timestamp']}:F> (<t:{request['timestamp']}:R>)\n"
        f"**Captain:** {request['requester_name']} ({request['requester_id']}) <@{request['requester_id']}>\n"
        f"**Event ID:** `{request['event_id']}`\n"
        f"**Notes:** {request['notes'] or 'None'}\n"
        f"-# Status: {request['status'].replace('_', ' ').title()}"
    )


def _preview_text(request: dict) -> str:
    return (
        "## Review Scrim Request\n"
        f"**From:** {request['requesting_team_name']}\n"
        f"**From Region:** {request['requesting_region_name']}\n"
        f"**To:** {request['target_team_name']}\n"
        f"**To Region:** {request['target_region_name']}\n"
        f"**Game:** {request['game_name']}\n"
        f"**Requested Time:** <t:{request['timestamp']}:F>\n"
        f"**Receiving Team Timezone:** {request['target_timezone']}\n"
        f"**Notes:** {request['notes'] or 'None'}\n\n"
        "Review these details carefully. Edit changes before sending."
    )


def _build_scrim_draft(guild: discord.Guild, requester: discord.abc.User, draft: dict) -> tuple[dict | None, str | None]:
    teams = get_teams(str(guild.id))
    requester_team = find_team_by_name(teams, draft["requesting_team"].strip())
    receiver_team = find_team_by_name(teams, draft["target_team"].strip())
    game_id = draft["game"].strip().lower()
    selected_game = get_game(game_id)
    if requester_team is None or receiver_team is None or selected_game is None:
        return None, "Select configured teams and a supported game."
    if requester_team is receiver_team:
        return None, "A team cannot request a scrim against itself."
    if requester.id != int(requester_team.get("team_captain_id", 0)):
        return None, "Only the requesting team's captain can request a scrim."
    if requester_team.get("game_id") != game_id or receiver_team.get("game_id") != game_id:
        return None, "Both teams must be assigned to the selected game."
    if not receiver_team.get("scrim_requests_enabled", True):
        return None, "That team is not accepting scrim requests."

    normalized_time = draft["time"].strip().replace(":", "").zfill(4)
    if not normalized_time.isdigit() or len(normalized_time) != 4:
        return None, "Invalid time format. Use hhmm, for example 1930."
    try:
        local_dt = datetime.strptime(f"{draft['date'].strip()} {normalized_time}", "%Y-%m-%d %H%M")
        event_dt = resolve_team_timezone(receiver_team).localize(local_dt)
    except ValueError:
        return None, "Invalid date or time. Use YYYY-MM-DD and hhmm."

    request_channel_id = receiver_team.get("team_request_channel")
    request_channel = guild.get_channel(request_channel_id) if request_channel_id else None
    if request_channel is None:
        return None, "The receiving team's request channel is unavailable."

    return {
        "requesting_team_name": requester_team["team_name"],
        "requesting_region_id": requester_team.get("region_id", ""),
        "requesting_region_name": get_region_name(requester_team.get("region_id", "")),
        "target_team_name": receiver_team["team_name"],
        "target_region_id": receiver_team.get("region_id", ""),
        "target_region_name": get_region_name(receiver_team.get("region_id", "")),
        "game_id": game_id,
        "game_name": selected_game["name"],
        "requester_id": requester.id,
        "requester_name": str(requester),
        "target_captain_id": int(receiver_team["team_captain_id"]),
        "target_schedule_channel_id": receiver_team.get("team_schedule_channel"),
        "target_role_id": receiver_team.get("team_role_id"),
        "target_timezone": receiver_team.get("timezone", "UTC"),
        "timestamp": int(event_dt.timestamp()),
        "datetime": event_dt.isoformat(),
        "notes": draft["notes"].strip()[:1000],
        "request_channel": request_channel,
    }, None


class ScrimEditModal(discord.ui.Modal):
    def __init__(self, preview: "ScrimPreviewView"):
        super().__init__(title="Edit Scrim Request")
        self.preview = preview
        self.requesting_team = discord.ui.TextInput(label="Requesting team", default=preview.draft["requesting_team"], max_length=100)
        self.game = discord.ui.TextInput(label="Game ID", default=preview.draft["game"], max_length=100)
        self.target_team = discord.ui.TextInput(label="Target team", default=preview.draft["target_team"], max_length=100)
        self.date = discord.ui.TextInput(label="Date (YYYY-MM-DD)", default=preview.draft["date"], max_length=10)
        self.time = discord.ui.TextInput(label="Time (hhmm, target timezone)", default=preview.draft["time"], max_length=5)
        for field in (self.requesting_team, self.game, self.target_team, self.date, self.time):
            self.add_item(field)

    async def on_submit(self, interaction: discord.Interaction):
        draft = {
            "requesting_team": str(self.requesting_team),
            "game": str(self.game),
            "target_team": str(self.target_team),
            "date": str(self.date),
            "time": str(self.time),
            "notes": self.preview.draft["notes"],
        }
        request, error = _build_scrim_draft(interaction.guild, interaction.user, draft)
        if error:
            await CommandResponse.error(interaction, error)
            return

        self.preview.draft = draft
        self.preview.request = request
        await interaction.response.defer(ephemeral=True)
        await self.preview.message.edit(content=_preview_text(request), view=self.preview)
        await interaction.followup.send("Scrim preview updated.", ephemeral=True)


class ScrimNotesModal(discord.ui.Modal):
    def __init__(self, preview: "ScrimPreviewView"):
        super().__init__(title="Edit Scrim Notes")
        self.preview = preview
        self.notes = discord.ui.TextInput(
            label="Notes",
            default=preview.draft["notes"],
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
        )
        self.add_item(self.notes)

    async def on_submit(self, interaction: discord.Interaction):
        draft = {**self.preview.draft, "notes": str(self.notes)}
        request, error = _build_scrim_draft(interaction.guild, interaction.user, draft)
        if error:
            await CommandResponse.error(interaction, error)
            return

        self.preview.draft = draft
        self.preview.request = request
        await interaction.response.defer(ephemeral=True)
        await self.preview.message.edit(content=_preview_text(request), view=self.preview)
        await interaction.followup.send("Scrim preview updated.", ephemeral=True)


class ScrimPreviewView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: str, requester_id: int, draft: dict, request: dict):
        super().__init__(timeout=900)
        self.bot = bot
        self.guild_id = guild_id
        self.requester_id = requester_id
        self.draft = draft
        self.request = request
        self.message = None

    async def _ensure_requester(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await CommandResponse.error(interaction, "Only the captain who created this preview can use it.")
        return False

    @discord.ui.button(label="Edit Details", style=discord.ButtonStyle.secondary)
    async def edit_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_requester(interaction):
            return
        self.message = interaction.message
        await interaction.response.send_modal(ScrimEditModal(self))

    @discord.ui.button(label="Edit Notes", style=discord.ButtonStyle.secondary)
    async def edit_notes(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_requester(interaction):
            return
        self.message = interaction.message
        await interaction.response.send_modal(ScrimNotesModal(self))

    @discord.ui.button(label="Send Request", style=discord.ButtonStyle.success)
    async def send_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_requester(interaction):
            return
        request, error = _build_scrim_draft(interaction.guild, interaction.user, self.draft)
        if error:
            await CommandResponse.error(interaction, error)
            return

        await interaction.response.defer(ephemeral=True)
        event_id = make_scrim_event_id(request["requesting_team_name"], request["target_team_name"], request["game_id"])
        request["event_id"] = event_id
        request["status"] = "pending"
        request_channel = request.pop("request_channel")
        request_message = await request_channel.send(
            f"<@{request['target_captain_id']}>\n{_request_text(request)}",
            view=ScrimRequestView(self.bot, self.guild_id, event_id),
        )
        request["request_message_id"] = request_message.id
        request["request_channel_id"] = request_channel.id
        save_scrim_request(self.guild_id, request)

        self.clear_items()
        await interaction.message.edit(content="## Scrim Request Sent\nYour request has been delivered to the receiving team's captain.", view=self)
        await interaction.followup.send(f"Scrim request sent to {request_channel.mention} with event ID `{event_id}`.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._ensure_requester(interaction):
            return
        self.clear_items()
        await interaction.response.edit_message(content="Scrim request cancelled. Nothing was sent.", view=self)


class ScrimRequestView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: str, event_id: str):
        super().__init__(timeout=604800)
        self.bot = bot
        self.guild_id = guild_id
        self.event_id = event_id

    def _can_respond(self, interaction: discord.Interaction, request: dict) -> bool:
        return interaction.user.id == request["target_captain_id"]

    @discord.ui.button(label="Check Availability", style=discord.ButtonStyle.primary)
    async def check_availability(self, interaction: discord.Interaction, button: discord.ui.Button):
        request = get_scrim_request(self.guild_id, self.event_id)
        if request is None:
            await CommandResponse.error(interaction, "This scrim request is no longer available.")
            return
        if not self._can_respond(interaction, request):
            await CommandResponse.error(interaction, "Only the receiving team's captain can check availability.")
            return
        if request["status"] != "pending":
            await CommandResponse.warning(interaction, "This scrim request has already been handled.")
            return

        event_cog = self.bot.get_cog("EventCog")
        channel = interaction.guild.get_channel(request["target_schedule_channel_id"])
        if event_cog is None or channel is None:
            await CommandResponse.error(interaction, "The team's schedule event channel is unavailable.")
            return

        await interaction.response.defer(ephemeral=True)
        event_data = {
            "event_name": f"Scrim availability: {request['requesting_team_name']}",
            "team_name": request["target_team_name"],
            "datetime": request["datetime"],
            "attend": [],
            "maybe": [],
            "cant": [],
            "scrim_event_id": self.event_id,
        }
        team_role_mention = f"<@&{request['target_role_id']}>" if request.get("target_role_id") else ""
        event_message = await channel.send("Creating scrim availability event...")
        event_view = EventRSVPLayoutView(
            event_cog=event_cog,
            guild_id=self.guild_id,
            message_id=event_message.id,
            event_data=event_data,
            team_role_mention=team_role_mention,
            unix_time=request["timestamp"],
            tz_name=request["target_timezone"],
        )
        await event_message.edit(content=None, view=event_view)
        events = event_cog.load_events(self.guild_id)
        events[str(event_message.id)] = event_data
        event_cog.save_events(self.guild_id, events)

        request = update_scrim_request(
            self.guild_id,
            self.event_id,
            status="availability_requested",
            availability_event_message_id=event_message.id,
            reviewed_by=interaction.user.id,
        )
        self.check_availability.disabled = True
        self.deny.disabled = True
        await interaction.message.edit(content=_request_text(request), view=self)

        try:
            requester = self.bot.get_user(request["requester_id"])
            if requester is None:
                requester = await self.bot.fetch_user(request["requester_id"])
            await requester.send(
                f"**{request['target_team_name']}** requested availability for your scrim request "
                f"`{request['event_id']}`. You can now coordinate directly with their captain."
            )
        except discord.HTTPException:
            pass
        await interaction.followup.send(f"Availability event created in {channel.mention}.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        request = get_scrim_request(self.guild_id, self.event_id)
        if request is None:
            await CommandResponse.error(interaction, "This scrim request is no longer available.")
            return
        if not self._can_respond(interaction, request):
            await CommandResponse.error(interaction, "Only the receiving team's captain can deny this request.")
            return
        if request["status"] != "pending":
            await CommandResponse.warning(interaction, "This scrim request has already been handled.")
            return

        request = update_scrim_request(
            self.guild_id,
            self.event_id,
            status="denied",
            reviewed_by=interaction.user.id,
        )
        self.check_availability.disabled = True
        self.deny.disabled = True
        await interaction.response.edit_message(content=_request_text(request), view=self)

        try:
            requester = self.bot.get_user(request["requester_id"])
            if requester is None:
                requester = await self.bot.fetch_user(request["requester_id"])
            await requester.send(
                f"Your scrim request `{request['event_id']}` to **{request['target_team_name']}** was denied."
            )
        except discord.HTTPException:
            pass


class ScrimCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def team_autocomplete(self, interaction: discord.Interaction, current: str):
        return build_team_name_choices(str(interaction.guild_id), current)

    async def game_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=f"{game['category']}: {game['name']}", value=game["id"])
            for game in get_games()
            if game.get("enabled", True) and current.lower() in f"{game['name']} {game['id']}".lower()
        ][:25]

    async def target_team_autocomplete(self, interaction: discord.Interaction, current: str):
        game_id = getattr(interaction.namespace, "game", "")
        return [
            app_commands.Choice(name=team["team_name"], value=team["team_name"])
            for team in get_teams(str(interaction.guild_id))
            if team.get("game_id") == game_id
            and team.get("scrim_requests_enabled", True)
            and current.lower() in team["team_name"].lower()
        ][:25]

    @app_commands.command(name="request_scrim", description="Request a scrim from a same-game team.")
    @app_commands.describe(
        requesting_team="Your team.",
        game="The game for this scrim.",
        target_team="A team accepting requests for this game.",
        date="Date in YYYY-MM-DD format.",
        time="Time in the receiving team's local hhmm 24-hour format.",
        notes="Optional details for the receiving captain.",
    )
    @app_commands.autocomplete(requesting_team=team_autocomplete, target_team=target_team_autocomplete, game=game_autocomplete)
    async def request_scrim(
        self,
        interaction: discord.Interaction,
        requesting_team: str,
        game: str,
        target_team: str,
        date: str,
        time: str,
        notes: str = "",
    ):
        draft = {
            "requesting_team": requesting_team,
            "game": game,
            "target_team": target_team,
            "date": date,
            "time": time,
            "notes": notes,
        }
        request, error = _build_scrim_draft(interaction.guild, interaction.user, draft)
        if error:
            await CommandResponse.error(interaction, error)
            return

        preview = ScrimPreviewView(self.bot, str(interaction.guild_id), interaction.user.id, draft, request)
        await interaction.response.send_message(_preview_text(request), view=preview, ephemeral=True)
        preview.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(ScrimCog(bot))