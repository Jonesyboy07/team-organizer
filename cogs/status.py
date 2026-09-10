import discord
from discord.ext import commands, tasks

from utils.owner_config import get_prefix_display, owner_only
from utils.status_store import (
    add_custom_status,
    disable_status,
    ensure_status_files,
    get_enabled_statuses,
    list_statuses,
    render_status,
)


class StatusCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._status_index = 0

    async def cog_load(self):
        ensure_status_files()
        if not self.rotate_status.is_running():
            self.rotate_status.start()

    async def cog_unload(self):
        if self.rotate_status.is_running():
            self.rotate_status.cancel()

    async def _apply_next_status(self) -> str:
        statuses = get_enabled_statuses()
        entry = statuses[self._status_index % len(statuses)]
        self._status_index += 1
        text = render_status(entry["text"], self.bot)
        await self.bot.change_presence(activity=discord.CustomActivity(name=text))
        return text

    @tasks.loop(minutes=20)
    async def rotate_status(self):
        await self._apply_next_status()

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        if getattr(self.bot, "_status_initialized", False):
            return
        self.bot._status_initialized = True
        await self._apply_next_status()

    @commands.command(name="status_list", help="Owner only: list rotating statuses.")
    @owner_only()
    async def status_list(self, ctx: commands.Context):
        entries = list_statuses()
        if not entries:
            await ctx.send("No rotating statuses are configured.")
            return

        lines = ["Rotating statuses:"]
        for entry in entries:
            state = "enabled" if entry.get("enabled", True) else "disabled"
            lines.append(f"- [{entry['source']}] {entry['text']} ({state})")
        await ctx.send("\n".join(lines)[:1900])

    @commands.command(name="status_add", help="Owner only: add or re-enable a rotating status.")
    @owner_only()
    async def status_add(self, ctx: commands.Context, *, text: str):
        created, entry = add_custom_status(text)
        action = "Added" if created else "Re-enabled"
        await ctx.send(f"{action} custom status: `{entry['text']}`")

    @commands.command(name="status_remove", help="Owner only: disable a rotating status by exact text.")
    @owner_only()
    async def status_remove(self, ctx: commands.Context, *, text: str):
        entry = disable_status(text)
        if entry is None:
            prefix = get_prefix_display(self.bot)
            await ctx.send(f"That status was not found. Use `{prefix}status_list` to copy the exact text.")
            return
        await ctx.send(f"Disabled {entry['source']} status: `{entry['text']}`")

    @commands.command(name="status_refresh", help="Owner only: force the next rotating status immediately.")
    @owner_only()
    async def status_refresh(self, ctx: commands.Context):
        text = await self._apply_next_status()
        await ctx.send(f"Status refreshed to: `{text}`")
