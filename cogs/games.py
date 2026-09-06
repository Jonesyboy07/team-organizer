import discord
from discord import app_commands
from discord.ext import commands

from utils.command_helpers import CommandResponse
from utils.game_service import (
    SUGGESTION_CHANNEL_ID,
    SUGGESTION_GUILD_ID,
    SUGGESTION_PING_USER_ID,
    add_suggestion,
    blacklist_suggester,
    get_games,
    is_suggestion_blacklisted,
    suggestion_cooldown_remaining,
)


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="games", description="List supported games by category.")
    async def games(self, interaction: discord.Interaction):
        games_by_category = {"VR": [], "PC": []}
        for game in get_games():
            if game.get("enabled", True):
                games_by_category.setdefault(game["category"], []).append(game)

        lines = []
        for category in ("VR", "PC"):
            games = games_by_category[category]
            game_lines = "\n".join(f"- `{game['id']}`: {game['name']}" for game in games) or "- No games yet."
            lines.append(f"## {category}\n{game_lines}")
        await interaction.response.send_message("\n\n".join(lines), ephemeral=True)

    @app_commands.command(name="suggest_game", description="Suggest a game for the central game catalog.")
    @app_commands.describe(game_name="The game's common name.")
    async def suggest_game(self, interaction: discord.Interaction, game_name: str):
        if interaction.guild_id != SUGGESTION_GUILD_ID:
            await CommandResponse.error(interaction, "Game suggestions are only accepted in the central server.")
            return
        if is_suggestion_blacklisted(interaction.user.id):
            await CommandResponse.error(interaction, "You are not allowed to submit game suggestions.")
            return

        remaining = suggestion_cooldown_remaining(interaction.user.id)
        if remaining:
            hours, remainder = divmod(remaining, 3600)
            minutes = remainder // 60
            await CommandResponse.warning(
                interaction,
                f"You can submit another suggestion in {hours}h {minutes}m.",
            )
            return

        normalized_name = game_name.strip()
        if not normalized_name or len(normalized_name) > 100:
            await CommandResponse.error(interaction, "Game names must be between 1 and 100 characters.")
            return

        suggestion = add_suggestion(interaction.user.id, normalized_name)
        channel = interaction.guild.get_channel(SUGGESTION_CHANNEL_ID)
        if channel is None:
            await CommandResponse.error(interaction, "The suggestion channel is unavailable. Please contact the server owner.")
            return

        await channel.send(
            f"<@{SUGGESTION_PING_USER_ID}>\n"
            f"## Game Suggestion\n"
            f"**Game:** {suggestion['game_name']}\n"
            f"**Suggested by:** {interaction.user.mention} ({interaction.user.id})\n"
            f"**Suggestion ID:** `{suggestion['id']}`"
        )
        await CommandResponse.success(interaction, "Your game suggestion was sent for review.")

    @app_commands.command(name="blacklist_game_suggester", description="Prevent a user from submitting central game suggestions.")
    async def blacklist_game_suggester(self, interaction: discord.Interaction, user: discord.Member):
        if interaction.guild_id != SUGGESTION_GUILD_ID or interaction.user.id != interaction.guild.owner_id:
            await CommandResponse.error(interaction, "Only this guild's owner can use this command.")
            return

        blacklist_suggester(user.id)
        await CommandResponse.success(interaction, f"{user.mention} can no longer submit game suggestions.")


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))