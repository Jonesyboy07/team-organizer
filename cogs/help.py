import discord
from discord.ext import commands
from discord import app_commands
import os
from os import path
from dotenv import load_dotenv
from utils.funcs import ReadJSON, CheckIfBotChannel
from utils.constants import INVITE_LINK
from utils.help_flow import HelpLayoutView

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
                "1. Use `/request_match` to request games.\n"
                "2. Use `/send_schedule` to post weekly availability prompts.\n"
                "3. Use `/event` to post RSVP event cards.\n\n"
                "### For Everyone\n"
                "Use `/help` for full command docs and `/my_teams` to see your linked teams."
            )
        )
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="help", description="Show help information")
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

    @app_commands.command(name="version", description="Show bot version")
    async def version_command(self, interaction: discord.Interaction):
        load_dotenv(dotenv_path=path.abspath(path.join(os.getcwd(), ".env")))
        version = os.getenv("VERSION", "Unknown")
        await interaction.response.send_message(
            f"Bot version: {version}", 
            ephemeral= not CheckIfBotChannel(
                interaction.channel_id, 
                interaction.guild_id
            )
        )

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping_command(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000  # Convert to milliseconds
        await interaction.response.send_message(
            f"Pong! Latency: {latency:.3f} ms",
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
            f"Invite the bot using this link: {INVITE_LINK}",
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