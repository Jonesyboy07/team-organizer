import os
from collections.abc import Callable
from functools import wraps

from discord.ext import commands
from dotenv import load_dotenv


def get_owner_id() -> int:
    load_dotenv()
    try:
        return int(os.getenv("OWNER_ID", "0"))
    except ValueError:
        return 0


def get_prefix_display(bot) -> str:
    prefix = getattr(bot, "command_prefix", "!")
    return prefix if isinstance(prefix, str) and prefix else "!"


def owner_only() -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, ctx: commands.Context, *args, **kwargs):
            owner_id = get_owner_id()
            if owner_id == 0:
                await ctx.send("OWNER_ID is not configured. Set OWNER_ID in .env and restart the bot.")
                return
            if ctx.author.id != owner_id:
                await ctx.send("You do not have permission to use this command.")
                return
            return await func(self, ctx, *args, **kwargs)

        return wrapper

    return decorator
