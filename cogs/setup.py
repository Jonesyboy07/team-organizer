import discord
from discord.ext import commands
from discord import app_commands

from utils.funcs import CheckIfAdminRole
from utils.server_store import get_server, read_servers, set_server, write_servers
from utils.command_helpers import (
    CommandResponse,
    log_command_execution,
)


class SetupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
            await log_command_execution(self.bot, guild_id, interaction.user, "setup", "ABORTED", "already completed")
            await CommandResponse.warning(
                interaction,
                "Setup has already been completed for this server.",
                hint="Use other commands to modify settings, or contact an admin to reset."
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

        await log_command_execution(self.bot, guild_id, interaction.user, "setup", "completed", f"{command_channel.mention} / {admin_role.mention}")

        card = discord.ui.LayoutView(timeout=180)
        container = discord.ui.Container(accent_color=discord.Color.green())
        container.add_item(discord.ui.TextDisplay("## ✅ Bot Setup Complete! 🎉"))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(discord.ui.TextDisplay(
            f"**Command Channel:** {command_channel.mention}\n"
            f"**Admin Role:** {admin_role.mention}\n"
            f"**Update Logs:** {update_logs.mention}\n"
            f"**Bot Logs:** {bot_logs.mention}"
        ))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(discord.ui.TextDisplay(
            "**Next Steps:**\n"
            "• Review Integrations tab to limit command visibility to trusted users\n"
            "• Use `/create_team` to add your first team\n"
            "• Run `/help` to see all available commands"
        ))
        card.add_item(container)
        await interaction.response.send_message(view=card, ephemeral=True)

    async def _check_admin_role(self, interaction: discord.Interaction) -> bool:
        """Check if user has admin role."""
        guild_id = str(interaction.guild.id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await CommandResponse.error(interaction, "You do not have permission.", hint="Admin role required.")
            return False
        return True

    async def _check_setup_complete(self, interaction: discord.Interaction) -> bool:
        """Check if server setup is complete."""
        guild_id = str(interaction.guild.id)
        if not get_server(guild_id).get("SetupComplete", False):
            await CommandResponse.error(interaction, "Server is not set up yet.", hint="Run `/setup` first.")
            return False
        return True

    async def _update_list_field(self, interaction: discord.Interaction, field_name: str, value: str, add: bool, field_label: str, mention: str):
        guild_id = str(interaction.guild.id)
        if not await self._check_admin_role(interaction):
            return

        if not await self._check_setup_complete(interaction):
            return

        server_data = get_server(guild_id)
        values = server_data.setdefault(field_name, [])
        
        if add:
            if value in values:
                await CommandResponse.warning(interaction, f"{field_label} {mention} is already configured.")
                return
            values.append(value)
            msg = f"Added {field_label} {mention}."
        else:
            if value not in values:
                await CommandResponse.warning(interaction, f"{field_label} {mention} is not configured.")
                return
            values.remove(value)
            msg = f"Removed {field_label} {mention}."

        set_server(guild_id, server_data)
        await CommandResponse.success(interaction, msg)

    @app_commands.command(name="addbotchannel", description="Add a bot command channel.")
    async def add_bot_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._update_list_field(interaction, "bot_channels", str(channel.id), True, "Bot Channel", channel.mention)

    @app_commands.command(name="removebotchannel", description="Remove a bot command channel.")
    async def remove_bot_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self._update_list_field(interaction, "bot_channels", str(channel.id), False, "Bot Channel", channel.mention)

    @app_commands.command(name="addadminrole", description="Add an admin role.")
    async def add_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        await self._update_list_field(interaction, "admin_roles", str(role.id), True, "Admin Role", role.mention)

    @app_commands.command(name="removeadminrole", description="Remove an admin role.")
    async def remove_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        await self._update_list_field(interaction, "admin_roles", str(role.id), False, "Admin Role", role.mention)

    async def _list_config_field(self, interaction: discord.Interaction, field_name: str, title: str, mention_prefix: str):
        """Display configured items in CV2 layout."""
        guild_id = str(interaction.guild.id)
        if not await self._check_admin_role(interaction):
            return

        server_data = get_server(guild_id)
        if not await self._check_setup_complete(interaction):
            return

        values = server_data.get(field_name, [])
        if not values:
            await CommandResponse.info(interaction, f"No {title.lower()} are configured.", hint=f"Use commands to add {title.lower()}.")
            return

        lines = "\n".join(f"{mention_prefix}{value}>" for value in values)
        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container(accent_color=discord.Color.blurple())
        container.add_item(discord.ui.TextDisplay(f"## {title}\n-# Total: {len(values)}"))
        container.add_item(discord.ui.TextDisplay(lines))
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="listbotchannels", description="List all configured bot channels.")
    async def list_bot_channels(self, interaction: discord.Interaction):
        await self._list_config_field(interaction, "bot_channels", "Bot Channels", "<#")

    @app_commands.command(name="listadminroles", description="List all configured admin roles.")
    async def list_admin_roles(self, interaction: discord.Interaction):
        await self._list_config_field(interaction, "admin_roles", "Admin Roles", "<@&")

    @app_commands.command(name="setbotlogchannel", description="Set or change the bot logging channel.")
    async def set_bot_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        if not await self._check_admin_role(interaction):
            return

        if not await self._check_setup_complete(interaction):
            return

        data = read_servers()
        server_data = data.get(guild_id, {})
        server_data["bot_logs_channel"] = str(channel.id)
        data[guild_id] = server_data
        write_servers(data)

        await CommandResponse.success(interaction, f"Bot log channel updated to {channel.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
