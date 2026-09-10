import asyncio

from discord.ext import commands

from utils.command_docs import sync_commands_json
from utils.owner_config import get_prefix_display, owner_only
from utils.server_store import ban_server, get_server, read_servers, set_team_creation_blacklist
from utils.version_store import write_version


def _read_update_text() -> str:
    with open("data/update.txt", "r", encoding="utf-8") as f:
        return f.read().strip()


def _normalize_server_id(server_id: str) -> str | None:
    cleaned = server_id.strip()
    return cleaned if cleaned.isdigit() else None


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
                    f"- `{prefix}update` — broadcast `data/update.txt`",
                    f"- `{prefix}uptime` — show bot uptime",
                    f"- `{prefix}status_list` — show rotating statuses",
                    f"- `{prefix}status_add <text>` — add or re-enable a custom status",
                    f"- `{prefix}status_remove <exact text>` — disable a status",
                    f"- `{prefix}status_refresh` — force the next rotating status now",
                    f"- `{prefix}a_server_count` — show how many servers the bot is in",
                    f"- `{prefix}a_servers` — list servers as name:id:teams:users",
                    f"- `{prefix}a_team_count` — show total team count across all servers",
                    f"- `{prefix}a_server_details <server_id>` — list team names in a server",
                    f"- `{prefix}a_team_blacklist <server_id>` — block team creation in a server",
                    f"- `{prefix}a_ban_server <server_id>` — ban a server and leave it",
                ]
            )
        )

    @commands.command(name="a_server_count", help="Owner only: show number of servers the bot is in.")
    @owner_only()
    async def a_server_count(self, ctx):
        await ctx.send(f"Server count: {len(self.bot.guilds)}")

    @commands.command(name="a_servers", help="Owner only: list servers as name:id:teams:users.")
    @owner_only()
    async def a_servers(self, ctx):
        if not self.bot.guilds:
            await ctx.send("The bot is not currently in any servers.")
            return

        servers = read_servers()
        lines = []
        for guild in sorted(self.bot.guilds, key=lambda g: g.name.lower()):
            server_data = servers.get(str(guild.id), {})
            team_count = len(server_data.get("teams", []))
            user_count = guild.member_count or 0
            lines.append(f"{guild.name}:{guild.id}:{team_count}:{user_count}")
        await ctx.send("\n".join(lines))

    @commands.command(name="a_team_count", help="Owner only: show total team count across all servers.")
    @owner_only()
    async def a_team_count(self, ctx):
        servers = read_servers()
        total = sum(len(server_data.get("teams", [])) for server_data in servers.values())
        await ctx.send(f"Team count: {total}")

    @commands.command(name="a_server_details", help="Owner only: list all team names in a server.")
    @owner_only()
    async def a_server_details(self, ctx, server_id: str):
        normalized = _normalize_server_id(server_id)
        if normalized is None:
            await ctx.send("Server ID must be numeric.")
            return

        server_data = get_server(normalized)
        teams = server_data.get("teams", [])
        if not teams:
            await ctx.send(f"No teams found for server `{normalized}`.")
            return
        team_names = [team.get("team_name", "Unnamed Team") for team in teams]
        await ctx.send(f"Teams in `{normalized}`:\n" + "\n".join(team_names))

    @commands.command(name="a_team_blacklist", help="Owner only: block team creation for a server ID.")
    @owner_only()
    async def a_team_blacklist(self, ctx, server_id: str):
        normalized = _normalize_server_id(server_id)
        if normalized is None:
            await ctx.send("Server ID must be numeric.")
            return
        set_team_creation_blacklist(normalized, True)
        await ctx.send(f"Team creation blacklisted for server `{normalized}`.")

    @commands.command(name="a_ban_server", help="Owner only: ban a server and leave it.")
    @owner_only()
    async def a_ban_server(self, ctx, server_id: str):
        normalized = _normalize_server_id(server_id)
        if normalized is None:
            await ctx.send("Server ID must be numeric.")
            return
        ban_server(normalized)
        guild = self.bot.get_guild(int(normalized))
        if guild is None:
            await ctx.send(f"Server `{normalized}` added to ban list.")
            return
        await guild.leave()
        await ctx.send(f"Server `{normalized}` banned and left.")

    @commands.command(name="set_version", help="Owner only: update the bot version text.")
    @owner_only()
    async def set_version(self, ctx, *, version: str):
        try:
            normalized = write_version(version)
        except ValueError as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Bot version updated to `{normalized}`")

    @commands.command(name="update", help="Send the latest update from data/update.txt to all update logs channels in every server.")
    @owner_only()
    async def update(self, ctx):
        print("Update command invoked by user:", ctx.author.id)
        try:
            servers = read_servers()
        except Exception as e:  # noqa: BLE001
            await ctx.send(f"Error reading server storage: {e}")
            return

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