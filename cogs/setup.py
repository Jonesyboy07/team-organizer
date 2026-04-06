import discord
from discord.ext import commands
from discord import app_commands

from utils.funcs import CheckIfAdminRole, log_to_discord
from utils.server_store import get_server, read_servers, set_server, write_servers


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _ensure_admin_role(self, interaction: discord.Interaction) -> bool:
        guild_id = str(interaction.guild.id)
        is_allowed = CheckIfAdminRole([role.id for role in interaction.user.roles], interaction.guild.id)
        if not is_allowed:
            await log_to_discord(
                self.bot,
                guild_id,
                f"Unauthorized {interaction.command.name} attempt by {interaction.user} ({interaction.user.id})",
            )
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return False
        return True

    async def _ensure_setup_complete(self, interaction: discord.Interaction, server_data: dict) -> bool:
        guild_id = str(interaction.guild.id)
        if not server_data.get("SetupComplete", False):
            await log_to_discord(self.bot, guild_id, f"{interaction.command.name} failed: setup incomplete ({interaction.user.id})")
            await interaction.response.send_message("Server is not set up yet. Please run /setup first.", ephemeral=True)
            return False
        return True

    @app_commands.command(name="setup", description="Set up the bot in this server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(
        self,
        interaction: discord.Interaction,
        command_channel: discord.TextChannel,
        admin_role: discord.Role,
        update_logs: discord.TextChannel,
        bot_logs: discord.TextChannel,
    ):
        guild_id = str(interaction.guild.id)
        existing = get_server(guild_id)
        if existing.get("SetupComplete", False):
            await log_to_discord(self.bot, guild_id, f"Setup attempted but already completed by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message(
                "Setup has already been completed for this server. Use other commands to modify settings.",
                ephemeral=True,
            )
            return

        set_server(
            guild_id,
            {
                "bot_channels": [str(command_channel.id)],
                "admin_roles": [str(admin_role.id)],
                "update_logs_channel": str(update_logs.id),
                "bot_logs_channel": str(bot_logs.id),
                "leagues": [],
                "teams": [],
                "SetupComplete": True,
            },
        )

        await log_to_discord(self.bot, guild_id, f"Setup completed by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(
            (
                f"Setup complete! Channel(s): {command_channel.mention}, Admin role(s): {admin_role.mention}.\n\n"
                "I recommend reviewing your Integrations command permissions so private commands are only visible to allowed users.\n\n"
                "Use /addbotchannel and /addadminrole to extend access.\n"
                "Use /removebotchannel and /removeadminrole to remove access.\n\n"
                "Run /help to see commands and usage."
            ),
            ephemeral=True,
        )

    async def _update_list_field(self, interaction: discord.Interaction, field_name: str, value: str, add: bool, mention: str):
        guild_id = str(interaction.guild.id)
        if not await self._ensure_admin_role(interaction):
            return

        server_data = get_server(guild_id)
        if not await self._ensure_setup_complete(interaction, server_data):
            return

        values = server_data.setdefault(field_name, [])
        if add:
            if value in values:
                await interaction.response.send_message(f"{mention} is already configured.", ephemeral=True)
                return
            values.append(value)
            action = "added"
        else:
            if value not in values:
                await interaction.response.send_message(f"{mention} is not configured.", ephemeral=True)
                return
            values.remove(value)
            action = "removed"

        set_server(guild_id, server_data)
        await log_to_discord(
            self.bot,
            guild_id,
            f"{field_name} value {value} {action} by {interaction.user} ({interaction.user.id})",
        )
        await interaction.response.send_message(f"{mention} has been {action}.", ephemeral=True)

    @app_commands.command(name="addbotchannel", description="Add a bot channel.")
    async def add_bot_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._update_list_field(interaction, "bot_channels", str(channel.id), True, channel.mention)

    @app_commands.command(name="removebotchannel", description="Remove a bot channel.")
    async def remove_bot_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._update_list_field(interaction, "bot_channels", str(channel.id), False, channel.mention)

    @app_commands.command(name="addadminrole", description="Add an admin role.")
    async def add_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        await self._update_list_field(interaction, "admin_roles", str(role.id), True, role.mention)

    @app_commands.command(name="removeadminrole", description="Remove an admin role.")
    async def remove_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        await self._update_list_field(interaction, "admin_roles", str(role.id), False, role.mention)

    async def _list_config_field(self, interaction: discord.Interaction, field_name: str, title: str, mention_prefix: str):
        guild_id = str(interaction.guild.id)
        if not await self._ensure_admin_role(interaction):
            return

        server_data = get_server(guild_id)
        if not await self._ensure_setup_complete(interaction, server_data):
            return

        values = server_data.get(field_name, [])
        if not values:
            await interaction.response.send_message(f"No {title.lower()} are configured.", ephemeral=True)
            return

        lines = "\n".join(f"{mention_prefix}{value}>" for value in values)
        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container(accent_color=discord.Color.blurple())
        container.add_item(discord.ui.TextDisplay(f"## {title}"))
        container.add_item(discord.ui.TextDisplay(lines))
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="listbotchannels", description="List all bot channels.")
    async def list_bot_channels(self, interaction: discord.Interaction):
        await self._list_config_field(interaction, "bot_channels", "Bot Channels", "<#")

    @app_commands.command(name="listadminroles", description="List all admin roles.")
    async def list_admin_roles(self, interaction: discord.Interaction):
        await self._list_config_field(interaction, "admin_roles", "Admin Roles", "<@&")

    @app_commands.command(name="setbotlogchannel", description="Set or change the bot logging channel.")
    async def set_bot_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        if not await self._ensure_admin_role(interaction):
            return

        data = read_servers()
        server_data = data.get(guild_id, {"SetupComplete": False})
        if not server_data.get("SetupComplete", False):
            await log_to_discord(self.bot, guild_id, f"setbotlogchannel failed: setup incomplete ({interaction.user.id})")
            await interaction.response.send_message("Server is not set up yet. Please run /setup first.", ephemeral=True)
            return

        old_channel = server_data.get("bot_logs_channel")
        server_data["bot_logs_channel"] = str(channel.id)
        data[guild_id] = server_data
        write_servers(data)

        await log_to_discord(
            self.bot,
            guild_id,
            f"Bot log channel changed from {old_channel} to {channel.id} by {interaction.user} ({interaction.user.id})",
        )
        await interaction.response.send_message(f"Bot log channel set to {channel.mention}.", ephemeral=True)
