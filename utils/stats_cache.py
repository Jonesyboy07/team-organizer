import json
import asyncio

async def cache_stats(bot, interval=600):
    while True:
        total_guilds = len(bot.guilds)
        total_users = len(set(bot.get_all_members()))
        stats = {
            "total_guilds": total_guilds,
            "total_users": total_users
        }
        with open("data/stats_hidden.json", "w") as f:
            json.dump(stats, f, indent=4)
        await asyncio.sleep(interval)