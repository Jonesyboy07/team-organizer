import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.funcs import CheckIfAdminRole, log_to_discord
from utils.command_helpers import CommandResponse
from datetime import datetime
import asyncio

from utils.schedule_flow import get_previous_monday, send_weekly_schedule_messages, register_persistent_daily_views
from utils.server_store import get_server, is_setup_complete, read_servers, write_servers
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

        await send_weekly_schedule_messages(channel, team_role_mention, monday)
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
        restored = register_persistent_daily_views(self.bot)
        if restored:
            print(f"[ScheduleCog] Re-registered {restored} persistent daily availability view(s).")

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

                        # Trigger every Monday between 12:00 and 12:02 local time
                        if now.weekday() == 0 and now.hour == 12 and now.minute < 2:
                            channel_id = team.get("team_schedule_channel")
                            channel = self.bot.get_channel(int(channel_id)) if channel_id else None

                            if channel:
                                team_role_id = team.get("team_role_id")
                                team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""
                                monday = get_previous_monday(now)
                                try:
                                    await send_weekly_schedule_messages(channel, team_role_mention, monday)
                                except Exception as e:
                                    await log_to_discord(self.bot, guild_id,
                                                         f"❌ Error sending automated schedule for {team.get('team_name')}: {e}")
                                    continue
                                await log_to_discord(self.bot, guild_id,
                                                     f"✅ Automated weekly schedule sent for team {team['team_name']}")
                                data = update_last_synced(data, guild_id, idx, today_str)
                                updated = True
                except Exception as e:
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
async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))
