import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import os
import json

from utils.event_flow import EventRSVPLayoutView
from utils.command_helpers import CommandResponse, validate_date_format
from utils.funcs import log_to_discord
from utils.server_store import get_teams
from utils.team_service import build_team_name_choices, find_team_by_name, resolve_team_timezone


class EventCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.events_folder = "data/events"
        os.makedirs(self.events_folder, exist_ok=True)

    def get_events_file(self, guild_id):
        return os.path.join(self.events_folder, f"{guild_id}.json")

    def load_events(self, guild_id):
        file_path = self.get_events_file(guild_id)
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        return {}

    def save_events(self, guild_id, events):
        file_path = self.get_events_file(guild_id)
        with open(file_path, "w") as f:
            json.dump(events, f, indent=4)

    async def team_autocomplete(self, interaction: discord.Interaction, current: str):
        return build_team_name_choices(str(interaction.guild_id), current)

    @app_commands.command(name="event", description="Create a team event with RSVP buttons.")
    @app_commands.describe(
        team_name="The team for the event.",
        date="The date for the event (YYYY-MM-DD).",
        time="The time for the event (hhmm, 24hr format, e.g. 0930).",
        event_name="The name of the event.",
    )
    @app_commands.autocomplete(team_name=team_autocomplete)
    async def event(
        self,
        interaction: discord.Interaction,
        team_name: str,
        date: str,
        time: str,
        event_name: str,
    ):
        guild_id = str(interaction.guild_id)
        teams = get_teams(guild_id)
        team = find_team_by_name(teams, team_name)
        if not team:
            await log_to_discord(
                self.bot,
                guild_id,
                f"Event creation failed: team '{team_name}' not found by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "Team was not found.",
                hint="Use an autocomplete option from /event team_name.",
            )
            return

        if not await validate_date_format(interaction, date):
            return

        tz_label = team.get("timezone", "UTC")
        tz = resolve_team_timezone(team)

        normalized_time = time.strip().replace(":", "")
        if not normalized_time.isdigit() or len(normalized_time) not in {3, 4}:
            await CommandResponse.error(
                interaction,
                "Invalid time format.",
                hint="Use hhmm in 24-hour time, for example 0930 or 1730.",
            )
            return
        normalized_time = normalized_time.zfill(4)

        try:
            event_date = datetime.strptime(date, "%Y-%m-%d")
            event_time = datetime.strptime(normalized_time, "%H%M")
            event_dt = event_date.replace(hour=event_time.hour, minute=event_time.minute)
            event_dt = tz.localize(event_dt)
        except Exception:
            await log_to_discord(
                self.bot,
                guild_id,
                f"Event creation failed: invalid date/time format by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "Date or time could not be parsed.",
                hint="Use date YYYY-MM-DD and time hhmm (24-hour).",
            )
            return

        unix_time = int(event_dt.timestamp())

        channel_id = team.get("team_schedule_channel")
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await log_to_discord(
                self.bot,
                guild_id,
                f"Event creation failed: schedule channel not found for team '{team_name}' by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "Team schedule channel was not found.",
                hint="Ask an admin to fix the team schedule channel in /modify_team.",
            )
            return

        team_role_id = team.get("team_role_id")
        team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""

        event_data = {
            "event_name": event_name,
            "team_name": team_name,
            "datetime": event_dt.isoformat(),
            "attend": [],
            "maybe": [],
            "cant": [],
        }

        message_obj = await channel.send("Creating event card...")
        view = EventRSVPLayoutView(
            event_cog=self,
            guild_id=guild_id,
            message_id=message_obj.id,
            event_data=event_data,
            team_role_mention=team_role_mention,
            unix_time=unix_time,
            tz_name=tz_label,
        )
        await message_obj.edit(content=None, view=view)

        events = self.load_events(guild_id)
        events[str(message_obj.id)] = event_data
        self.save_events(guild_id, events)

        await log_to_discord(
            self.bot,
            guild_id,
            f"Event '{event_name}' created for team '{team_name}' by {interaction.user} ({interaction.user.id}) in channel {channel.mention}",
        )
        await CommandResponse.success(
            interaction,
            f"Event card created in {channel.mention}.",
        )


async def setup(bot):
    await bot.add_cog(EventCog(bot))
