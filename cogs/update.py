from discord.ext import commands
from utils.funcs import ReadJSON
from utils.command_docs import sync_commands_json
import os
from dotenv import load_dotenv


def _owner_id() -> int:
    load_dotenv()
    try:
        return int(os.getenv("OWNER_ID", "0"))
    except ValueError:
        return 0

class UpdateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="sync_commands",
        help="Owner only: globally sync slash commands to Discord.",
    )
    async def sync_commands(self, ctx):
        owner_id = _owner_id()
        if owner_id == 0:
            await ctx.send("OWNER_ID is not configured. Set OWNER_ID in .env and restart the bot.")
            return

        if ctx.author.id != owner_id:
            await ctx.send("You do not have permission to use this command.")
            return

        try:
            synced = await self.bot.tree.sync()
        except Exception as e:
            await ctx.send(f"Command sync failed: {e}")
            return

        names = ", ".join(command.name for command in synced[:15])
        extra = "" if len(synced) <= 15 else f" (+{len(synced) - 15} more)"
        await ctx.send(f"Synced {len(synced)} slash command(s): {names}{extra}")

    @commands.command(
        name="refresh_help_docs",
        help="Owner only: regenerate data/commands.json from currently loaded slash commands.",
    )
    async def refresh_help_docs(self, ctx):
        owner_id = _owner_id()
        if owner_id == 0:
            await ctx.send("OWNER_ID is not configured. Set OWNER_ID in .env and restart the bot.")
            return

        if ctx.author.id != owner_id:
            await ctx.send("You do not have permission to use this command.")
            return

        count = sync_commands_json(self.bot)
        await ctx.send(f"Regenerated data/commands.json from {count} slash command(s).")

    @commands.command(name="update", help="Send the latest update from data/update.txt to all update logs channels in every server.")
    async def update(self, ctx):
        print("Update command invoked by user:", ctx.author.id)
        if ctx.author.id != _owner_id():
            await ctx.send("You do not have permission to use this command.")
            return

        try:
            servers = ReadJSON("data/servers.json")
        except Exception as e:
            await ctx.send(f"Error reading servers.json: {e}")
            return

        try:
            with open("data/update.txt", "r", encoding="utf-8") as f:
                update_text = f.read().strip()
        except FileNotFoundError:
            await ctx.send("No update.txt file found in the data folder.")
            return
        except Exception as e:
            await ctx.send(f"Error reading update.txt: {e}")
            return

        sent_count = 0
        failed_guilds = []
        for guild_id, server_data in servers.items():
            update_channel_id = server_data.get("update_logs_channel")
            if not update_channel_id:
                failed_guilds.append(guild_id)
                continue
            try:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    failed_guilds.append(guild_id)
                    continue
                channel = guild.get_channel(int(update_channel_id))
                if not channel:
                    failed_guilds.append(guild_id)
                    continue
                await channel.send(f"📢 **Update:**\n{update_text}")
                sent_count += 1
            except Exception as e:
                failed_guilds.append(guild_id)
                print(e)
                continue

        msg = f"Update sent to {sent_count} update logs channel(s)."
        if failed_guilds:
            msg += f"\nFailed to send to {len(failed_guilds)} server(s): {', '.join(failed_guilds)}"
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))