import asyncio
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.command_helpers import CommandResponse
from utils.funcs import CheckIfAdminRole, log_to_discord
from utils.schedule_flow import (
    fetch_day_availability,
    get_previous_monday,
    get_schedule_event,
    list_schedule_events,
    send_weekly_schedule_messages,
)
from utils.server_store import (
    get_server,
    is_setup_complete,
    read_servers,
    write_servers,
)
from utils.team_service import resolve_team_timezone


def update_last_synced(servers, guild_id, team_idx, today_str):
    current_server = servers.get(guild_id, {})
    teams = current_server.get("teams", [])
    if team_idx < len(teams):
        teams[team_idx]["last_synced"] = today_str
        current_server["teams"] = teams
        servers[guild_id] = current_server
    return servers


class TeamScheduleDropdown(discord.ui.Select):
    def __init__(self, teams):
        options = [discord.SelectOption(label=t["team_name"], value=str(i)) for i, t in enumerate(teams)]
        super().__init__(placeholder="Select a team to send scheduling...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        idx = int(self.values[0])
        team = self.view.teams[idx]
        tz = resolve_team_timezone(team)

        now = datetime.now(tz)
        monday = get_previous_monday(now)
        channel_id = team.get("team_schedule_channel")

        channel = None
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))

        if not channel:
            await log_to_discord(self.view.bot, str(interaction.guild_id),
                                 f"Schedule channel not found for {team['team_name']} by {interaction.user}")
            await CommandResponse.followup_error(
                interaction,
                f"Schedule channel not found for **{team['team_name']}**.",
                hint="Ask an admin to set one via `/modify_team`.",
            )
            return

        team_role_id = team.get("team_role_id")
        team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""

        await send_weekly_schedule_messages(channel, team_role_mention, monday, team)
        await log_to_discord(self.view.bot, str(interaction.guild_id),
                             f"Manual weekly schedule sent for {team['team_name']} by {interaction.user}")

        today_str = now.strftime("%Y-%m-%d")
        guild_id = str(interaction.guild_id)
        servers = read_servers()
        servers = update_last_synced(servers, guild_id, idx, today_str)
        write_servers(servers)

        await CommandResponse.followup_success(interaction, f"Weekly scheduling messages sent for **{team['team_name']}**.")


class TeamScheduleView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=60)
        self.teams = teams
        self.add_item(TeamScheduleDropdown(teams))
        self.bot = None


class ScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schedule_lock = asyncio.Lock()

    async def cog_load(self):
        """Automatically start loop when cog is loaded."""
        if not self.schedule_core.is_running():
            self.schedule_core.start()
            print("[ScheduleCog] Background scheduling task started.")

    async def cog_unload(self):
        """Stops the loop cleanly when the cog is unloaded."""
        if self.schedule_core.is_running():
            self.schedule_core.cancel()
            print("[ScheduleCog] Background scheduling task stopped.")

    @tasks.loop(minutes=1)
    async def schedule_core(self):
        async with self.schedule_lock:
            try:
                data = read_servers()
            except FileNotFoundError:
                data = {}

            updated = False

            for guild_id, guild_data in data.items():
                if not guild_data.get("SetupComplete", False):
                    continue

                try:
                    for idx, team in enumerate(guild_data.get("teams", [])):
                        tz = resolve_team_timezone(team)

                        now = datetime.now(tz)
                        today_str = now.strftime("%Y-%m-%d")

                        if team.get("last_synced") == today_str:
                            continue

                        # Trigger every Sunday between 12:00 and 12:02 local time
                        if now.weekday() == 6 and now.hour == 12 and now.minute < 2:
                            channel_id = team.get("team_schedule_channel")
                            channel = self.bot.get_channel(int(channel_id)) if channel_id else None

                            if channel:
                                team_role_id = team.get("team_role_id")
                                team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""
                                monday = get_previous_monday(now + timedelta(days=1))
                                try:
                                    await send_weekly_schedule_messages(channel, team_role_mention, monday, team)
                                except Exception as e:  # noqa: BLE001
                                    await log_to_discord(self.bot, guild_id,
                                                         f"❌ Error sending automated schedule for {team.get('team_name')}: {e}")
                                    continue
                                await log_to_discord(self.bot, guild_id,
                                                     f"✅ Automated weekly schedule sent for team {team['team_name']}")
                                data = update_last_synced(data, guild_id, idx, today_str)
                                updated = True
                except Exception as e:  # noqa: BLE001
                    await log_to_discord(self.bot, guild_id, f"Schedule loop error in guild {guild_id}: {e}")

            if updated:
                write_servers(data)
                print("[ScheduleCog] Schedule data updated and written to file.")

    @app_commands.command(name="send_schedule", description="Send a scheduling message for a team (admin or team captain only).")
    async def send_schedule(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [r.id for r in interaction.user.roles]
        current_server = get_server(guild_id)
        if not is_setup_complete(guild_id):
            await CommandResponse.warning(interaction, "Bot is not set up yet.", hint="Run `/setup` first.")
            return

        teams = current_server.get("teams", [])
        if not teams:
            await CommandResponse.info(interaction, "No teams found.", hint="Use `/create_team` to add one.")
            return

        allowed_team_idxs = []
        for idx, team in enumerate(teams):
            if CheckIfAdminRole(user_roles, guild_id) or int(interaction.user.id) == int(team.get("team_captain_id", 0)):
                allowed_team_idxs.append(idx)

        if not allowed_team_idxs:
            await CommandResponse.error(
                interaction,
                "You do not have permission to send scheduling.",
                hint="Only admin roles and team captains can use this.",
            )
            return

        allowed_teams = [teams[idx] for idx in allowed_team_idxs]
        view = TeamScheduleView(allowed_teams)
        view.bot = self.bot
        await interaction.response.send_message("Select a team to send scheduling for:", view=view, ephemeral=True)

    async def event_id_autocomplete(self, interaction: discord.Interaction, current: str):
        guild_id = str(interaction.guild_id)
        events = list_schedule_events(guild_id)
        current_lower = current.lower()
        choices = []
        for eid, event in events.items():
            label = f"{eid} - {event.get('team_name', 'Unknown')} ({event.get('start_date', '')})"
            if current_lower in eid.lower() or current_lower in event.get("team_name", "").lower():
                choices.append(app_commands.Choice(name=label[:100], value=eid))
        return choices[:25]

    @app_commands.command(name="check_availability", description="Fetch who is available for each day of a scheduling event (admin or team captain only).")
    @app_commands.describe(event_id="The 6-character event ID from the scheduling message footer.")
    @app_commands.autocomplete(event_id=event_id_autocomplete)
    async def check_availability(self, interaction: discord.Interaction, event_id: str):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild_id)
        event = get_schedule_event(guild_id, event_id)
        if not event:
            await CommandResponse.followup_error(interaction, f"No scheduling event found with ID `{event_id}`.")
            return

        user_roles = [r.id for r in interaction.user.roles]
        team_captain_id = int(event.get("team_captain_id") or 0)
        if not (CheckIfAdminRole(user_roles, guild_id) or interaction.user.id == team_captain_id):
            await CommandResponse.followup_error(
                interaction,
                "You do not have permission to view this event's availability.",
                hint="Only admin roles and the team captain can use this.",
            )
            return

        channel = interaction.guild.get_channel(int(event.get("channel_id") or 0))
        if not channel:
            await CommandResponse.followup_error(interaction, "The schedule channel for this event no longer exists.")
            return

        team_role = interaction.guild.get_role(int(event.get("team_role_id") or 0))
        roster = [m for m in team_role.members if not m.bot] if team_role else []

        lines = [f"## Availability for **{event.get('team_name', 'Unknown team')}** — Event `{event_id}`"]

        for date_str, message_id in sorted(event.get("days", {}).items()):
            available_ids, unavailable_ids, partial_ids = await fetch_day_availability(channel, message_id)

            available, unavailable, partial, no_response = [], [], [], []
            for member in roster:
                if member.id in available_ids:
                    available.append(member.mention)
                elif member.id in unavailable_ids:
                    unavailable.append(member.mention)
                elif member.id in partial_ids:
                    partial.append(member.mention)
                else:
                    no_response.append(member.mention)

            day_label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A %d %B")  # noqa: DTZ007
            lines.append(f"\n**{day_label}**")
            lines.append(f"✅ Available all day: {', '.join(available) if available else 'None'}")
            lines.append(f"❌ Unavailable all day: {', '.join(unavailable) if unavailable else 'None'}")
            lines.append(f"⏰ Partial availability: {', '.join(partial) if partial else 'None'}")
            lines.append(f"❔ No response: {', '.join(no_response) if no_response else 'None'}")

        content = "\n".join(lines)
        for i in range(0, len(content), 3500):
            await CommandResponse.followup_info(interaction, content[i:i + 3500])


async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))
