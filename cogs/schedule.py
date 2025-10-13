import discord
from discord.ext import commands, tasks
from discord import app_commands
from utils.funcs import WriteJSON, ReadJSON, CheckIfAdminRole, log_to_discord
from datetime import datetime, timedelta
import pytz
import asyncio

def get_previous_monday(dt):
    # If today is Monday, return today; else, return previous Monday
    return dt - timedelta(days=dt.weekday())

def get_number_emojis():
    """Returns the list of number emojis for 1 to 10."""
    return [
        "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"
    ]

def build_intro_embed(team_role_mention, start_date):
    number_emojis = get_number_emojis()
    time_labels = [
        "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM", "7 PM", "8 PM",
        "9 PM", "10 PM"
    ]
    times_str = "\n".join([f"{emoji} = {label}" for emoji, label in zip(number_emojis, time_labels)])
    embed = discord.Embed(
        title="Weekly Scheduling",
        description=(
            f"{team_role_mention}\n"
            f"**{start_date.strftime('%A: The %d of %B')}**\n\n"
            "Scheduling for this week!\n"
            "Each day will have a message for you to react to, indicating your availability for that day.\n"
            "Time slots run from **1 PM to 10 PM**.\n"
            "React to each day's message using the number emojis below:\n\n"
            f"{times_str}\n"
        ),
        color=discord.Color.blue()
    )
    embed.set_footer(text="React to each day's message to indicate your availability.")
    return embed

def build_day_message(*args):
    """
    Accepts either:
      - build_day_message(date_str)
      - build_day_message(team_role_mention, date_str)
    Returns a message string with optional role mention on top.
    """
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
    # Send intro embed (with ping)
    embed = build_intro_embed(team_role_mention, start_date)
    await channel.send(content=team_role_mention, embed=embed)

    number_emojis = get_number_emojis()
    # Send a message for each day (Monday to Sunday), no ping
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
    teams[team_idx]["last_synced"] = today_str
    current_server["teams"] = teams
    servers[guild_id] = current_server
    return servers

class TeamScheduleDropdown(discord.ui.Select):
    def __init__(self, teams):
        options = [
            discord.SelectOption(label=team["team_name"], value=str(idx))
            for idx, team in enumerate(teams)
        ]
        super().__init__(placeholder="Select a team to send scheduling...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # Prevent timeout error

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
        try:
            channel = interaction.guild.get_channel(int(channel_id)) if channel_id is not None else None
        except (ValueError, TypeError):
            channel = None
        if not channel:
            await log_to_discord(self.view.bot, str(interaction.guild_id), f"Schedule channel not found for team {team['team_name']} by {interaction.user} ({interaction.user.id})")
            await interaction.followup.send("Schedule channel not found.", ephemeral=True)
            return

        team_role_id = team.get("team_role")
        team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""

        await send_weekly_schedule_messages(channel, team_role_mention, monday)
        await log_to_discord(self.view.bot, str(interaction.guild_id), f"Weekly scheduling messages sent for team {team['team_name']} by {interaction.user} ({interaction.user.id})")

        # Update last_synced for today (Monday)
        today_str = now.strftime("%Y-%m-%d")
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        servers = update_last_synced(servers, guild_id, idx, today_str)
        WriteJSON(servers, "data/servers.json")

        await interaction.followup.send(
            f"Weekly scheduling messages sent for **{team['team_name']}**.", ephemeral=True
        )

class TeamScheduleView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=60)
        self.teams = teams
        self.add_item(TeamScheduleDropdown(teams))
        # Pass bot instance for logging
        self.bot = None

class ScheduleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.schedule_lock = asyncio.Lock()

    @tasks.loop(minutes=1)
    async def schedule_core(self):
        async with self.schedule_lock:
            filename = "data/servers.json"
            try:
                data = ReadJSON(filename)
            except FileNotFoundError:
                data = {}

            updated = False

            for guild_id, guild_data in data.items():
                if not guild_data.get("SetupComplete", False):
                    continue

                for idx, team in enumerate(guild_data.get("teams", [])):
                    tz_name = team.get("timezone", "UTC")
                    try:
                        tz = pytz.timezone(tz_name)
                    except pytz.UnknownTimeZoneError:
                        tz = pytz.UTC

                    now = datetime.now(tz)
                    today_str = now.strftime("%Y-%m-%d")

                    # Check last_synced
                    last_synced = team.get("last_synced")
                    if last_synced == today_str:
                        continue

                    if now.weekday() == 0 and now.hour == 12 and now.minute == 0:
                        channel_id = team.get("team_schedule_channel")
                        try:
                            channel = self.bot.get_channel(int(channel_id)) if channel_id is not None else None
                        except (ValueError, TypeError):
                            channel = None
                        if channel:
                            team_role_id = team.get("team_role")
                            team_role_mention = f"<@&{team_role_id}>" if team_role_id else ""
                            date_str = now.strftime("%A: The %d of %B")
                            try:
                                await send_schedule_message(channel, team_role_mention, date_str)
                            except Exception as e:
                                await log_to_discord(self.bot, guild_id, f"Error sending automated schedule for team {team.get('team_name')}: {e}")
                                continue
                            await log_to_discord(self.bot, guild_id, f"Automated weekly schedule sent for team {team['team_name']} in guild {guild_id}")
                            # Update last_synced
                            data = update_last_synced(data, guild_id, idx, today_str)
                            updated = True

            if updated:
                WriteJSON(data, filename)

    @app_commands.command(name="send_schedule", description="Send a scheduling message for a team (admin or team captain only).")
    async def send_schedule(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        if not current_server.get("SetupComplete", False):
            await log_to_discord(self.bot, guild_id, f"send_schedule failed: bot not setup by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("Bot not setup yet.", ephemeral=True)
            return
        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(self.bot, guild_id, f"send_schedule failed: no teams found by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("No teams found.", ephemeral=True)
            return

        # Only allow admins or team captains to use
        allowed_team_idxs = []
        for idx, team in enumerate(teams):
            if CheckIfAdminRole(user_roles, guild_id) or team.get("team_cap_role") in user_roles:
                allowed_team_idxs.append(idx)
        if not allowed_team_idxs:
            await log_to_discord(self.bot, guild_id, f"send_schedule failed: no permission for any team by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("You do not have permission to send scheduling for any team.", ephemeral=True)
            return

        allowed_teams = [teams[idx] for idx in allowed_team_idxs]
        view = TeamScheduleView(allowed_teams)
        view.bot = self.bot  # Pass bot instance for logging in dropdown
        await log_to_discord(self.bot, guild_id, f"send_schedule command used by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message("Select a team to send scheduling for:", view=view, ephemeral=True)

async def send_schedule_message(channel, team_role_mention, date_str):
    msg_content = build_day_message(team_role_mention, date_str)
    number_emojis = get_number_emojis()
    message = await channel.send(msg_content)
    for emoji in number_emojis:
        await message.add_reaction(emoji)

