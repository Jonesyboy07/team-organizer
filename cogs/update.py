import asyncio

from discord.ext import commands

from utils.command_docs import sync_commands_json
from utils.owner_config import get_prefix_display, owner_only
from utils.server_store import read_servers
from utils.version_store import write_version


def _read_update_text() -> str:
    with open("data/update.txt", "r", encoding="utf-8") as f:
        return f.read().strip()


def _write_update_text(update_text: str) -> str:
    normalized = update_text.strip()
    if not normalized:
        raise ValueError("Update text cannot be empty.")
    with open("data/update.txt", "w", encoding="utf-8") as f:
        f.write(normalized)
    return normalized

class UpdateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="sync_commands",
        help="Owner only: globally sync slash commands to Discord.",
    )
    @owner_only()
    async def sync_commands(self, ctx):
        try:
            synced = await self.bot.tree.sync()
        except Exception as e:  # noqa: BLE001
            await ctx.send(f"Command sync failed: {e}")
            return

        names = ", ".join(command.name for command in synced[:15])
        extra = "" if len(synced) <= 15 else f" (+{len(synced) - 15} more)"
        await ctx.send(f"Synced {len(synced)} slash command(s): {names}{extra}")

    @commands.command(
        name="refresh_help_docs",
        help="Owner only: regenerate data/commands.json from currently loaded slash commands.",
    )
    @owner_only()
    async def refresh_help_docs(self, ctx):
        count = sync_commands_json(self.bot)
        await ctx.send(f"Regenerated data/commands.json from {count} slash command(s).")

    @commands.command(name="a_help", help="Owner only: list bot owner prefix commands.")
    @owner_only()
    async def owner_help(self, ctx):
        prefix = get_prefix_display(self.bot)
        await ctx.send(
            "\n".join(
                [
                    "Owner commands:",
                    f"- `{prefix}a_help` — list owner commands",
                    f"- `{prefix}sync_commands` — sync slash commands to Discord",
                    f"- `{prefix}refresh_help_docs` — rebuild `data/commands.json`",
                    f"- `{prefix}set_version <value>` — update `data/version.txt`",
                    f"- `{prefix}update [text]` — save text (optional) and broadcast update",
                    f"- `{prefix}uptime` — show bot uptime",
                    f"- `{prefix}status_list` — show rotating statuses",
                    f"- `{prefix}status_add <text>` — add or re-enable a custom status",
                    f"- `{prefix}status_remove <exact text>` — disable a status",
                    f"- `{prefix}status_refresh` — force the next rotating status now",
                ]
            )
        )

    @commands.command(name="set_version", help="Owner only: update the bot version text.")
    @owner_only()
    async def set_version(self, ctx, *, version: str):
        try:
            normalized = write_version(version)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Bot version updated to `{normalized}`")

    @commands.command(
        name="update",
        help="Owner only: send update text to configured channels. Optionally pass text to save into data/update.txt first.",
    )
    @owner_only()
    async def update(self, ctx, *, update_text_arg: str | None = None):
        print("Update command invoked by user:", ctx.author.id)
        try:
            servers = read_servers()
        except Exception as e:  # noqa: BLE001
            await ctx.send(f"Error reading server storage: {e}")
            return

        if update_text_arg is not None:
            try:
                update_text = await asyncio.to_thread(_write_update_text, update_text_arg)
            except ValueError as exc:
                await ctx.send(str(exc))
                return
            except Exception as e:  # noqa: BLE001
                await ctx.send(f"Error saving update.txt: {e}")
                return
        else:
            try:
                update_text = await asyncio.to_thread(_read_update_text)
            except FileNotFoundError:
                await ctx.send("No update.txt file found in the data folder.")
                return
            except Exception as e:  # noqa: BLE001
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
            except Exception as e:  # noqa: BLE001
                failed_guilds.append(guild_id)
                print(e)
                continue

        msg = f"Update sent to {sent_count} update logs channel(s)."
        if failed_guilds:
            msg += f"\nFailed to send to {len(failed_guilds)} server(s): {', '.join(failed_guilds)}"
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(UpdateCog(bot))