import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.funcs import WriteJSON, ReadJSON, CheckIfAdminRole, log_to_discord
from datetime import datetime, timedelta
import pytz
import asyncio


def get_previous_monday(dt):
    return dt - timedelta(days=dt.weekday())


def get_number_emojis():
    return ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def build_intro_embed(team_role_mention, start_date):
    number_emojis = get_number_emojis()
    time_labels = [
        "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM",
        "7 PM", "8 PM", "9 PM", "10 PM"
    ]
    times_str = "\n".join([f"{emoji} = {label}" for emoji, label in zip(number_emojis, time_labels)])
    embed = discord.Embed(
        title="Weekly Scheduling",
        description=(
            f"{team_role_mention}\n"
            f"**{start_date.strftime('%A: The %d of %B')}**\n\n"
            "Scheduling for this week!\n"
            "Each day will have a message for you to react to.\n"
            "Time slots run from **1 PM to 10 PM**.\n"
            f"React with the emojis below:\n\n{times_str}"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="React to each day's message to indicate your availability.")
    return embed


def build_day_message(*args):
    if len(args) == 1:
        date_str = args[0]
        return f"**{date_str}**"
    elif len(args) == 2:
        team_role_mention, date_str = args
        prefix = f"{team_role_mention}\n" if team_role_mention else ""
        return f"{prefix}**{date_str}**"
    else:
        raise TypeError("build_day_message expects 1 or 2 arguments")


async def send_weekly_schedule_messages(channel, team_role_mention, start_date):
    embed = build_intro_embed(team_role_mention, start_date)
    await channel.send(content=team_role_mention, embed=embed)

    number_emojis = get_number_emojis()
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        day_str = day_date.strftime("%A: The %d of %B")
        msg_content = build_day_message(day_str)
        message = await channel.send(msg_content)
        for emoji in number_emojis:
            await message.add_reaction(emoji)


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
        tz_name = team.get("timezone", "UTC")
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.UTC

        now = datetime.now(tz)
        monday = get_previous_monday(now)
        channel_id = team.get("team_schedule_channel")

        channel = None
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))

        if not channel:
            await log_to_discord(self.view.bot, str(interaction.guild_id),
                                 f"Schedule channel not found for {team['team_name']} by {interaction.user}")
            await interaction.followup.send("Schedule channel not found.", ephemeral=True)
            return

        team_role_id = team.get("team_role_id")
        team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""

        await send_weekly_schedule_messages(channel, team_role_mention, monday)
        await log_to_discord(self.view.bot, str(interaction.guild_id),
                             f"Manual weekly schedule sent for {team['team_name']} by {interaction.user}")

        today_str = now.strftime("%Y-%m-%d")
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        servers = update_last_synced(servers, guild_id, idx, today_str)
        WriteJSON(servers, "data/servers.json")

        await interaction.followup.send(f"✅ Weekly scheduling messages sent for **{team['team_name']}**.", ephemeral=True)


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
                data = ReadJSON("data/servers.json")
            except FileNotFoundError:
                data = {}

            updated = False
            print("[ScheduleCog] Running automated schedule check...")

            for guild_id, guild_data in data.items():
                if not guild_data.get("SetupComplete", False):
                    continue

                try:
                    for idx, team in enumerate(guild_data.get("teams", [])):
                        tz_name = team.get("timezone", "UTC")
                        try:
                            tz = pytz.timezone(tz_name)
                        except pytz.UnknownTimeZoneError:
                            tz = pytz.UTC

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
                WriteJSON(data, "data/servers.json")
                print("[ScheduleCog] Schedule data updated and written to file.")

    @app_commands.command(name="send_schedule", description="Send a scheduling message for a team (admin or team captain only).")
    async def send_schedule(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [r.id for r in interaction.user.roles]
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        if not current_server.get("SetupComplete", False):
            await interaction.response.send_message("⚠️ Bot not setup yet.", ephemeral=True)
            return

        teams = current_server.get("teams", [])
        if not teams:
            await interaction.response.send_message("No teams found.", ephemeral=True)
            return

        allowed_team_idxs = []
        for idx, team in enumerate(teams):
            if CheckIfAdminRole(user_roles, guild_id) or int(interaction.user.id) == int(team.get("team_captain_id", 0)):
                allowed_team_idxs.append(idx)

        if not allowed_team_idxs:
            await interaction.response.send_message("You do not have permission to send scheduling.", ephemeral=True)
            return

        allowed_teams = [teams[idx] for idx in allowed_team_idxs]
        view = TeamScheduleView(allowed_teams)
        view.bot = self.bot
        await interaction.response.send_message("Select a team to send scheduling for:", view=view, ephemeral=True)


async def send_schedule_message(channel, team_role_mention, date_str):
    msg_content = build_day_message(team_role_mention, date_str)
    number_emojis = get_number_emojis()
    message = await channel.send(msg_content)
    for emoji in number_emojis:
        await message.add_reaction(emoji)


async def setup(bot):
    await bot.add_cog(ScheduleCog(bot))
