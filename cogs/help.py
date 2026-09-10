from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.command_helpers import CommandResponse
from utils.constants import INVITE_LINK
from utils.funcs import CheckIfBotChannel, ReadJSON
from utils.help_flow import HelpLayoutView
from utils.owner_config import owner_only
from utils.version_store import read_version


def _format_duration(total_seconds: int) -> str:
    hours, remaining = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remaining, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)
class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="quickstart", description="Show a quick getting-started guide.")
    async def quickstart_command(self, interaction: discord.Interaction):
        view = discord.ui.LayoutView(timeout=120)
        container = discord.ui.Container(accent_color=discord.Color.teal())
        container.add_item(discord.ui.TextDisplay("## Quickstart"))
        container.add_item(
            discord.ui.TextDisplay(
                "### For Server Admins\n"
                "1. Run `/setup` and set channels/roles.\n"
                "2. Create teams with `/create_team`.\n"
                "3. Check config with `/listbotchannels` and `/listadminroles`.\n\n"
                "### For Team Captains\n"
                "1. Use `/set_team_game` to assign your team's game.\n"
                "2. Use `/set_scrim_requests` to control incoming scrim requests.\n"
                "3. Use `/request_scrim` to request a same-game scrim.\n"
                "4. Use `/send_schedule` to post weekly availability prompts.\n\n"
                "### For Everyone\n"
                "Use `/games` to browse supported games, `/suggest_game` to suggest one, "
                "and `/help` for full command docs."
            )
        )
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="help", description="Show help information")
    @app_commands.checks.cooldown(1, 10.0)
    async def help_command(self, interaction: discord.Interaction):
        sections = ReadJSON("data/commands.json")["sections"]
        view = HelpLayoutView(sections)
        await interaction.response.send_message(
            view=view,
            ephemeral= not CheckIfBotChannel(
                interaction.channel_id,
                interaction.guild_id
            )
        )

    @app_commands.command(name="version", description="Show the bot version.")
    async def version_command(self, interaction: discord.Interaction):
        version = read_version()
        await interaction.response.send_message(f"Bot version: **{version}**", ephemeral=True)

    @commands.command(name="uptime", help="Owner only: show when the bot started and its uptime.")
    @owner_only()
    async def uptime_command(self, ctx: commands.Context):
        started_at = getattr(self.bot, "started_at", datetime.now(timezone.utc))
        elapsed_seconds = int((datetime.now(timezone.utc) - started_at).total_seconds())
        started_timestamp = int(started_at.timestamp())
        await ctx.send(
            f"Started: <t:{started_timestamp}:F> (<t:{started_timestamp}:R>)\n"
            f"Uptime: **{_format_duration(elapsed_seconds)}**"
        )

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping_command(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000  # Convert to milliseconds
        await interaction.response.send_message(
            f"🏓 Pong! Latency: **{latency:.3f} ms**",
            ephemeral= not CheckIfBotChannel(
                interaction.channel_id,
                interaction.guild_id
            )
        )
        
    @app_commands.command(name="info", description="Show bot information")
    async def info_command(self, interaction: discord.Interaction):
        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container(accent_color=discord.Color.green())
        container.add_item(discord.ui.TextDisplay("## Bot Information"))
        container.add_item(
            discord.ui.TextDisplay(
                "This bot helps manage teams, scheduling, events, and match requests.\n\n"
                "**Developer:** Jonesy\n"
                "**Support:** https://github.com/Jonesyboy07/team-organizer/issues\n"
                "**GitHub:** https://github.com/Jonesyboy07/team-organizer\n"
                f"**Invite:** {INVITE_LINK}\n"
                "**Donation:** https://ko-fi.com/jonesy_alr"
            )
        )
        view.add_item(container)
        await interaction.response.send_message(
            view=view,
            ephemeral=True
        )
        
    @app_commands.command(name="invite", description="Get the bot invite link")
    async def invite_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"ℹ️ Invite the bot using this link: {INVITE_LINK}",
            ephemeral= not CheckIfBotChannel(
                interaction.channel_id,
                interaction.guild_id
            )
        )
    
    @app_commands.command(name="stats", description="Show bot statistics")
    async def stats_command(self, interaction: discord.Interaction):
        total_guilds = len(self.bot.guilds)
        total_users = len(set(self.bot.get_all_members()))
        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container(accent_color=discord.Color.blurple())
        container.add_item(discord.ui.TextDisplay("## Bot Statistics"))
        container.add_item(
            discord.ui.TextDisplay(
                f"**Total Servers:** {total_guilds}\n"
                f"**Total Users:** {total_users}"
            )
        )
        view.add_item(container)
        await interaction.response.send_message(
            view=view,
            ephemeral= not CheckIfBotChannel(
                interaction.channel_id,
                interaction.guild_id
            )
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        command_name = getattr(interaction.command, "name", "")
        if command_name == "help" and isinstance(error, app_commands.CommandOnCooldown):
            retry_after = max(1, round(error.retry_after))
            message = f"Help is rate limited right now. Try again in about {retry_after} second(s)."
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
            return
        raise error
