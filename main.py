import os
from dotenv import load_dotenv

import discord
from discord.ext import commands
from cogs.init import get_cogs
from utils.stats_cache import cache_stats
from utils.command_docs import sync_commands_json

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
clientid = os.getenv("DISCORD_CLIENT_ID")
prefix = os.getenv("PREFIX", "!")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.message_content = True
client = commands.Bot(command_prefix=prefix,
                    intents=intents,
                    help_command=None, 
                    application_id=clientid)

# Event: When the bot is ready
@client.event
async def on_ready():
    print("Bot is online")
    print(f"Logged in as: {client.user} - {client.user.id}")
    client.loop.create_task(cache_stats(client))
    # await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="The Number One Free Scheduling Bot"))
    print("----------------------------")
    print(f"We are in the following guild(s) - ({len(client.guilds)}):")
    for guild in client.guilds:
        print(f"- {guild.name} (id: {guild.id})")

    if not getattr(client, "_commands_docs_synced", False):
        cmd_count = sync_commands_json(client)
        client._commands_docs_synced = True
        print(f"Auto-synced data/commands.json with {cmd_count} slash command(s)")

# Load cogs
async def load_cogs():
    for cog in get_cogs(client):
        await client.add_cog(cog)
        print(f"Added commands from {cog.__class__.__name__}:")
        for command in cog.get_commands():
            print(f"- {command.name}")

# Sync commands on startup
async def setup_hook():
    await load_cogs()

client.setup_hook = setup_hook

# Run the bot
client.run(token)
