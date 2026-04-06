import discord
from discord.ext import commands
from utils.server_store import read_servers, write_servers, set_server


class JoinedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        set_server(guild.id, {"SetupComplete": False})

        target = guild.system_channel
        if target is None:
            target = next(
                (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                None,
            )
        if target is None:
            return

        view = discord.ui.LayoutView(timeout=None)
        container = discord.ui.Container(accent_color=discord.Color.teal())
        container.add_item(discord.ui.TextDisplay(f"## 👋 Welcome to {guild.name}!"))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(
            discord.ui.TextDisplay(
                "Thanks for adding the bot! Here's how to get started:\n\n"
                "**Step 1:** Run `/setup` to configure bot channels and admin roles.\n"
                "**Step 2:** Use `/create_team` to add your first team.\n"
                "**Step 3:** Use `/help` or `/quickstart` for full command documentation.\n\n"
                "-# Tip: Use `/listbotchannels` and `/listadminroles` to review your config at any time."
            )
        )
        view.add_item(container)
        await target.send(view=view)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        guild_id = str(guild.id)
        data = read_servers()
        if guild_id in data:
            del data[guild_id]
            write_servers(data)