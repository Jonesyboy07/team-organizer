import discord
from discord.ext import commands
from discord import app_commands

from utils.constants import MAJOR_TIMEZONES
from utils.command_helpers import CommandResponse, validate_date_format
from utils.funcs import CheckIfAdminRole, log_to_discord
from utils.match_request_flow import MatchRequestSetupView
from utils.server_store import get_server, get_teams, is_setup_complete, set_server
from utils.team_service import build_team_name_choices, find_team_by_name
from utils.team_manage_flow import TeamDeleteView, TeamListView, TeamModifyView


class TeamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=tz, value=tz)
            for tz in MAJOR_TIMEZONES
            if current.lower() in tz.lower()
        ][:25]

    async def team_name_autocomplete(self, interaction: discord.Interaction, current: str):
        return build_team_name_choices(str(interaction.guild_id), current)

    @app_commands.command(name="my_teams", description="Show teams you are part of or captain of.")
    async def my_teams(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        teams = get_teams(guild_id)
        if not teams:
            await CommandResponse.info(
                interaction,
                "No teams are configured yet.",
            )
            return

        member_role_ids = {role.id for role in interaction.user.roles}
        mine = []
        for team in teams:
            captain_id = int(team.get("team_captain_id", 0))
            team_role_id = int(team.get("team_role_id", 0)) if team.get("team_role_id") else 0
            if interaction.user.id == captain_id or (team_role_id and team_role_id in member_role_ids):
                mine.append(team)

        if not mine:
            await CommandResponse.info(
                interaction,
                "You are not linked to any configured team roles or captain slots.",
                hint="Ask an admin to set your team role or captain assignment.",
            )
            return

        view = discord.ui.LayoutView(timeout=120)
        container = discord.ui.Container(accent_color=discord.Color.gold())
        container.add_item(discord.ui.TextDisplay("## My Teams"))

        lines = []
        for team in mine:
            schedule_channel = interaction.guild.get_channel(team.get("team_schedule_channel"))
            request_channel = interaction.guild.get_channel(team.get("team_request_channel"))
            role = interaction.guild.get_role(team.get("team_role_id"))
            lines.append(
                f"### {team.get('team_name', 'Unknown')}\n"
                f"Game: {team.get('game', 'Unknown')}\n"
                f"Role: {role.mention if role else 'Not set'}\n"
                f"Schedule Channel: {schedule_channel.mention if schedule_channel else 'Not set'}\n"
                f"Match Request Channel: {request_channel.mention if request_channel else 'Not set'}"
            )

        container.add_item(discord.ui.TextDisplay("\n\n".join(lines)))
        view.add_item(container)
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="create_team", description="Create a new team")
    @app_commands.autocomplete(timezone=timezone_autocomplete)
    async def create_team(
        self,
        interaction: discord.Interaction,
        team_name: str,
        game: str,
        team_captain: discord.Member,
        team_role: discord.Role,
        team_schedule_channel: discord.TextChannel,
        team_request_channel: discord.TextChannel,
        timezone: str,
    ):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"Unauthorized create_team attempt by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "You do not have permission to create teams.",
                hint="Only configured admin roles can use this command.",
            )
            return

        current_server = get_server(guild_id)
        if not is_setup_complete(guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"create_team failed: bot not setup by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "Server setup is incomplete.",
                hint="Run /setup first.",
            )
            return

        teams = current_server.get("teams", [])
        if any(t.get("team_name", "").lower() == team_name.lower() for t in teams):
            await CommandResponse.warning(
                interaction,
                f"A team named '{team_name}' already exists.",
            )
            return

        team_data = {
            "team_name": team_name,
            "game": game,
            "team_captain_id": team_captain.id,
            "team_role_id": team_role.id,
            "team_schedule_channel": team_schedule_channel.id,
            "team_request_channel": team_request_channel.id,
            "timezone": timezone,
            "created_at": str(interaction.created_at),
        }
        teams.append(team_data)
        current_server["teams"] = teams
        set_server(guild_id, current_server)

        await log_to_discord(
            self.bot,
            guild_id,
            f"Team '{team_name}' created for '{game}' by {interaction.user} ({interaction.user.id})",
        )
        card = discord.ui.LayoutView(timeout=120)
        container = discord.ui.Container(accent_color=discord.Color.green())
        container.add_item(discord.ui.TextDisplay(f"## ✅ Team Created: {team_name}"))
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(discord.ui.TextDisplay(
            f"**Game:** {game}\n"
            f"**Captain:** {team_captain.mention}\n"
            f"**Role:** {team_role.mention}\n"
            f"**Schedule Channel:** {team_schedule_channel.mention}\n"
            f"**Request Channel:** {team_request_channel.mention}\n"
            f"**Timezone:** {timezone}"
        ))
        card.add_item(container)
        await interaction.response.send_message(view=card, ephemeral=True)

    @app_commands.command(name="list_teams", description="List all teams in this server.")
    @app_commands.describe(per_page="Number of teams per page (default 5, max 25)")
    async def list_teams(self, interaction: discord.Interaction, per_page: int = 5):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"Unauthorized list_teams attempt by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "You do not have permission to list teams.",
                hint="Only configured admin roles can use this command.",
            )
            return

        current_server = get_server(guild_id)
        if not is_setup_complete(guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"list_teams failed: bot not setup by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "Server setup is incomplete.",
                hint="Run /setup first.",
            )
            return

        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(
                self.bot,
                guild_id,
                f"list_teams: no teams found by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.info(
                interaction,
                "No teams are configured yet.",
                hint="Use /create_team to add your first team.",
            )
            return

        view = TeamListView(teams, interaction, per_page=per_page)
        await log_to_discord(self.bot, guild_id, f"Teams listed by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(name="delete_team", description="Delete a team from this server.")
    async def delete_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"Unauthorized delete_team attempt by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "You do not have permission to delete teams.",
                hint="Only configured admin roles can use this command.",
            )
            return

        current_server = get_server(guild_id)
        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(
                self.bot,
                guild_id,
                f"delete_team: no teams to delete by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.info(
                interaction,
                "There are no teams to delete.",
            )
            return

        view = TeamDeleteView(teams)
        await log_to_discord(self.bot, guild_id, f"Team delete view sent by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message("Select a team to delete:", view=view, ephemeral=True)

    @app_commands.command(name="modify_team", description="Modify a team's details.")
    async def modify_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(
                self.bot,
                guild_id,
                f"Unauthorized modify_team attempt by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.error(
                interaction,
                "You do not have permission to modify teams.",
                hint="Only configured admin roles can use this command.",
            )
            return

        current_server = get_server(guild_id)
        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(
                self.bot,
                guild_id,
                f"modify_team: no teams found by {interaction.user} ({interaction.user.id})",
            )
            await CommandResponse.info(
                interaction,
                "No teams are configured yet.",
                hint="Use /create_team to add your first team.",
            )
            return

        view = TeamModifyView(teams, interaction.guild, 0)
        await log_to_discord(self.bot, guild_id, f"Team modify view sent by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(content=f"Modify team: **{teams[0]['team_name']}**", view=view, ephemeral=True)

    @app_commands.command(name="request_match", description="Request a match from another team (including teams outside this server).")
    @app_commands.describe(
        requesting_team="Your team name (must be configured in this server).",
        target_team="Target team name (can be from another server).",
        date="Match date in YYYY-MM-DD format.",
        notes="Optional notes for the request.",
    )
    @app_commands.autocomplete(requesting_team=team_name_autocomplete)
    async def request_match(
        self,
        interaction: discord.Interaction,
        requesting_team: str,
        target_team: str,
        date: str,
        notes: str = "",
    ):
        guild_id = str(interaction.guild_id)
        current_server = get_server(guild_id)
        if not is_setup_complete(guild_id):
            await CommandResponse.error(
                interaction,
                "Server setup is incomplete.",
                hint="Run /setup first.",
            )
            return

        if not await validate_date_format(interaction, date):
            return

        teams = current_server.get("teams", [])
        if not teams:
            await CommandResponse.info(
                interaction,
                "No teams are configured yet.",
                hint="Use /create_team before requesting matches.",
            )
            return

        requester_team = find_team_by_name(teams, requesting_team)
        receiver_team = find_team_by_name(teams, target_team)

        if requester_team is None:
            await CommandResponse.error(
                interaction,
                "Requesting team was not found.",
                hint="Use an autocomplete option from the command list.",
            )
            return

        if receiver_team is not None and requester_team.get("team_name") == receiver_team.get("team_name"):
            await CommandResponse.warning(
                interaction,
                "You cannot request a match against the same team.",
            )
            return

        user_roles = [role.id for role in interaction.user.roles]
        is_admin = CheckIfAdminRole(user_roles, guild_id)
        is_captain = interaction.user.id == int(requester_team.get("team_captain_id", 0))
        if not is_admin and not is_captain:
            await CommandResponse.error(
                interaction,
                "You must be an admin or the requesting team's captain to do this.",
                hint="Ask your team captain or an admin to submit the request.",
            )
            return

        if receiver_team is None:
            # External target: keep request flow in the requesting team's channel.
            target_team_name = target_team.strip()
            target_team_captain_id = 0
            request_channel_id = requester_team.get("team_request_channel")
            request_channel = interaction.guild.get_channel(int(request_channel_id)) if request_channel_id else None
            if request_channel is None:
                await log_to_discord(
                    self.bot,
                    guild_id,
                    f"request_match failed: external target '{target_team}' but requesting team channel missing for {requester_team.get('team_name')}",
                )
                await CommandResponse.error(
                    interaction,
                    "External match request could not be posted because your team has no valid request channel.",
                    hint="Ask an admin to set your team request channel via /modify_team.",
                )
                return
        else:
            target_team_name = receiver_team.get("team_name", target_team)
            target_team_captain_id = int(receiver_team.get("team_captain_id", 0))
            request_channel_id = receiver_team.get("team_request_channel")
            request_channel = interaction.guild.get_channel(int(request_channel_id)) if request_channel_id else None
            if request_channel is None:
                await log_to_discord(
                    self.bot,
                    guild_id,
                    f"request_match failed: request channel missing for target team {receiver_team.get('team_name')}",
                )
                await CommandResponse.error(
                    interaction,
                    "Target team has no valid match request channel configured.",
                    hint="An admin can set it via /modify_team.",
                )
                return

        view = MatchRequestSetupView(
            bot=self.bot,
            guild_id=guild_id,
            requester=interaction.user,
            requesting_team_name=requester_team.get("team_name", requesting_team),
            target_team_name=target_team_name,
            target_team_captain_id=target_team_captain_id,
            request_channel=request_channel,
            request_date=date,
            notes=notes,
        )

        await log_to_discord(
            self.bot,
            guild_id,
            f"request_match setup opened by {interaction.user} ({interaction.user.id}) for "
            f"{requesting_team} -> {target_team_name} on {date}",
        )
        await interaction.response.send_message(
            "Select the requested time and timezone, then submit.",
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TeamCog(bot))
