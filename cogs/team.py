import discord
from discord.ext import commands
from discord import app_commands
from utils.funcs import ReadJSON, WriteJSON, CheckIfAdminRole, log_to_discord
import math

# ---------- CONSTANTS ----------
from utils.constants import MAJOR_TIMEZONES

# ---------- DELETE TEAM ----------

class TeamDeleteDropdown(discord.ui.Select):
    def __init__(self, teams):
        options = [discord.SelectOption(label=team["team_name"], value=str(idx)) for idx, team in enumerate(teams)]
        super().__init__(placeholder="Select a team to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: TeamDeleteView = self.view
        idx = int(self.values[0])
        team = view.teams[idx]
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        teams = current_server.get("teams", [])
        teams.pop(idx)
        current_server["teams"] = teams
        servers[guild_id] = current_server
        WriteJSON(servers, "data/servers.json")
        await log_to_discord(interaction.client, guild_id, f"Team '{team['team_name']}' deleted by {interaction.user} ({interaction.user.id})")
        await interaction.response.edit_message(content=f"Team '{team['team_name']}' deleted.", view=None, embed=None)

class TeamDeleteView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=60)
        self.teams = teams
        self.add_item(TeamDeleteDropdown(teams))

# ---------- MODIFY TEAM ----------

class TeamModifyView(discord.ui.View):
    """Main modify view for a specific team with looping."""
    def __init__(self, teams, guild: discord.Guild, team_idx: int, root_view=None):
        super().__init__(timeout=180)
        self.teams = teams
        self.guild = guild
        self.team_idx = team_idx

        self.root_view = root_view if root_view else self

        # Field dropdown
        self.field_dropdown = TeamFieldDropdownLoop(teams, team_idx, guild, self)
        self.add_item(self.field_dropdown)

        # Close button
        close_btn = discord.ui.Button(label="Close", style=discord.ButtonStyle.danger)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

        # Home button (go to root modify)
        home_btn = discord.ui.Button(label="Home", style=discord.ButtonStyle.primary)
        home_btn.callback = self.go_home
        self.add_item(home_btn)

        # Team select button
        team_select_btn = discord.ui.Button(label="Change Team", style=discord.ButtonStyle.secondary)
        team_select_btn.callback = self.change_team
        self.add_item(team_select_btn)

    async def close_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Modification session closed.", view=None)
        self.stop()

    async def go_home(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content=f"Modify team: **{self.teams[self.team_idx]['team_name']}**", view=self.root_view)

    async def change_team(self, interaction: discord.Interaction):
        # Display the team select dropdown again
        options = [discord.SelectOption(label=t["team_name"], value=str(i)) for i,t in enumerate(self.teams)]
        class TeamSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(placeholder="Select a team to modify...", min_values=1, max_values=1, options=options)
            async def callback(self_inner, i: discord.Interaction):
                idx = int(self_inner.values[0])
                view = TeamModifyView(self.teams, interaction.guild, idx)
                await i.response.edit_message(content=f"Modifying team: **{self.teams[idx]['team_name']}**", view=view)
        view = discord.ui.View()
        view.add_item(TeamSelect())
        await interaction.response.edit_message(content="Select a team to modify:", view=view)

class MemberSelectLoop(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        super().__init__(placeholder="Select new Team Captain...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        new_member_id = int(self.values[0])
        team = self.teams[self.team_idx]
        team[self.field] = new_member_id
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        current_server["teams"] = self.teams
        servers[guild_id] = current_server
        WriteJSON(servers, "data/servers.json")
        member = interaction.guild.get_member(new_member_id)
        await log_to_discord(interaction.client, guild_id, f"Updated {self.field} for team '{team['team_name']}' to member '{member.display_name if member else new_member_id}' by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"Updated **Team Captain** to **{member.mention if member else new_member_id}** for team **{team['team_name']}**.", ephemeral=True)
        await interaction.edit_original_response(view=self.parent_view)

class TeamFieldDropdownLoop(discord.ui.Select):
    """Dropdown for selecting a field to modify."""
    def __init__(self, teams, team_idx, guild: discord.Guild, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.guild = guild
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="Team Name", value="team_name"),
            discord.SelectOption(label="Game", value="game"),
            discord.SelectOption(label="Team Captain", value="team_captain_id"),
            discord.SelectOption(label="Team Role", value="team_role_id"),
            discord.SelectOption(label="Schedule Channel", value="team_schedule_channel"),
            discord.SelectOption(label="Timezone", value="timezone")
        ]
        super().__init__(placeholder="Select a field to modify...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        field = self.values[0]
        team = self.teams[self.team_idx]
        view = discord.ui.View()

        # Team Captain
        if field == "team_captain_id":
            member_options = [discord.SelectOption(label=m.display_name, value=str(m.id)) for m in self.guild.members]
            member_select = MemberSelectLoop(self.teams, self.team_idx, field, member_options, self.parent_view)
            view.add_item(member_select)

        # Team Role
        elif field == "team_role_id":
            role_options = [discord.SelectOption(label=r.name, value=str(r.id)) for r in self.guild.roles]
            role_select = RoleSelectLoop(self.teams, self.team_idx, field, role_options, self.parent_view)
            view.add_item(role_select)

        # Channels
        elif field == "team_schedule_channel":
            channel_options = [discord.SelectOption(label=c.name, value=str(c.id)) for c in self.guild.text_channels]
            channel_select = ChannelSelectLoop(self.teams, self.team_idx, field, channel_options, self.parent_view)
            view.add_item(channel_select)

        # Timezone (paginated)
        elif field == "timezone":
            tz_select = TimezoneSelectPaginated(self.teams, self.team_idx, field, self.parent_view)
            await interaction.response.edit_message(content=f"Select timezone for **{team['team_name']}**:", view=tz_select)
            return

        # Text fields
        else:
            await interaction.response.send_modal(TeamModifyModalLoop(self.teams, self.team_idx, field, team.get(field, "")))
            return

        # Home button
        home_btn = discord.ui.Button(label="Home", style=discord.ButtonStyle.primary)
        async def home_callback(i: discord.Interaction):
            await i.response.edit_message(content=f"Modify team: **{team['team_name']}**", view=self.parent_view)
        home_btn.callback = home_callback
        view.add_item(home_btn)

        # Team select button
        team_select_btn = discord.ui.Button(label="Change Team", style=discord.ButtonStyle.secondary)
        async def team_callback(i: discord.Interaction):
            options = [discord.SelectOption(label=t["team_name"], value=str(idx)) for idx,t in enumerate(self.teams)]
            class TeamSelect(discord.ui.Select):
                def __init__(self_inner):
                    super().__init__(placeholder="Select a team to modify...", min_values=1, max_values=1, options=options)
                async def callback(self_inner, interaction2: discord.Interaction):
                    idx2 = int(self_inner.values[0])
                    new_view = TeamModifyView(self.teams, interaction.guild, idx2)
                    await interaction2.response.edit_message(content=f"Modifying team: **{self.teams[idx2]['team_name']}**", view=new_view)
            new_view = discord.ui.View()
            new_view.add_item(TeamSelect())
            await i.response.edit_message(content="Select a team to modify:", view=new_view)
        team_select_btn.callback = team_callback
        view.add_item(team_select_btn)

        await interaction.response.edit_message(content=f"Modify **{field.replace('_',' ').title()}**:", view=view)

# ---------- ROLE/CHANNEL/TIMEZONE/TEXT HANDLERS ----------

class RoleSelectLoop(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        super().__init__(placeholder=f"Select new {field.replace('_',' ').title()}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        new_role_id = int(self.values[0])
        team = self.teams[self.team_idx]
        team[self.field] = new_role_id
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        current_server["teams"] = self.teams
        servers[guild_id] = current_server
        WriteJSON(servers, "data/servers.json")
        role = interaction.guild.get_role(new_role_id)
        await log_to_discord(interaction.client, guild_id, f"Updated {self.field} for team '{team['team_name']}' to role '{role.name if role else new_role_id}' by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"Updated **Team Role** to **{role.mention if role else new_role_id}** for team **{team['team_name']}**.", ephemeral=True)
        await interaction.edit_original_response(view=self.parent_view)

class ChannelSelectLoop(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        super().__init__(placeholder=f"Select new {field.replace('_',' ').title()}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        new_channel_id = int(self.values[0])
        team = self.teams[self.team_idx]
        team[self.field] = new_channel_id
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        current_server["teams"] = self.teams
        servers[guild_id] = current_server
        WriteJSON(servers, "data/servers.json")
        channel = interaction.guild.get_channel(new_channel_id)
        await log_to_discord(interaction.client, guild_id, f"Updated {self.field} for team '{team['team_name']}' to channel '{channel.name}' by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"Updated **{self.field.replace('_',' ').title()}** to **{channel.name}** for team **{team['team_name']}**.", ephemeral=True)
        await interaction.edit_original_response(view=self.parent_view)

class TimezoneSelectPaginated(discord.ui.View):
    """Shows paginated dropdown for timezones (10 per page)."""
    def __init__(self, teams, team_idx, field, parent_view):
        super().__init__(timeout=180)
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        self.page = 0
        self.per_page = 10
        self.max_page = math.ceil(len(MAJOR_TIMEZONES)/self.per_page) - 1
        self.update_dropdown()

        # Pagination buttons
        self.prev_btn = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.prev_btn.callback = self.prev_page
        self.next_btn.callback = self.next_page
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)

        # Home and team select
        home_btn = discord.ui.Button(label="Home", style=discord.ButtonStyle.primary)
        home_btn.callback = self.go_home
        self.add_item(home_btn)

        team_select_btn = discord.ui.Button(label="Change Team", style=discord.ButtonStyle.secondary)
        team_select_btn.callback = self.change_team
        self.add_item(team_select_btn)

    def update_dropdown(self):
        start = self.page * self.per_page
        end = start + self.per_page
        tz_options = [discord.SelectOption(label=tz, value=tz) for tz in MAJOR_TIMEZONES[start:end]]
        self.clear_items()
        self.tz_dropdown = TimezoneSelectDropdown(self.teams, self.team_idx, self.field, tz_options, self.parent_view, self)
        self.add_item(self.tz_dropdown)

    async def prev_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_dropdown()
            await interaction.response.edit_message(content=f"Select timezone for **{self.teams[self.team_idx]['team_name']}**:", view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.page < self.max_page:
            self.page += 1
            self.update_dropdown()
            await interaction.response.edit_message(content=f"Select timezone for **{self.teams[self.team_idx]['team_name']}**:", view=self)

    async def go_home(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content=f"Modify team: **{self.teams[self.team_idx]['team_name']}**", view=self.parent_view)

    async def change_team(self, interaction: discord.Interaction):
        options = [discord.SelectOption(label=t["team_name"], value=str(idx)) for idx,t in enumerate(self.teams)]
        class TeamSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(placeholder="Select a team to modify...", min_values=1, max_values=1, options=options)
            async def callback(self_inner, i: discord.Interaction):
                idx2 = int(self_inner.values[0])
                new_view = TeamModifyView(self.teams, i.guild, idx2)
                await i.response.edit_message(content=f"Modifying team: **{self.teams[idx2]['team_name']}**", view=new_view)
        view = discord.ui.View()
        view.add_item(TeamSelect())
        await interaction.response.edit_message(content="Select a team to modify:", view=view)

class TimezoneSelectDropdown(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view, parent_paginated_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        self.parent_paginated_view = parent_paginated_view
        super().__init__(placeholder="Select a timezone...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        tz = self.values[0]
        team = self.teams[self.team_idx]
        team[self.field] = tz
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        current_server["teams"] = self.teams
        servers[guild_id] = current_server
        WriteJSON(servers, "data/servers.json")
        await log_to_discord(interaction.client, guild_id, f"Updated timezone for team '{team['team_name']}' to '{tz}' by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"Updated timezone for **{team['team_name']}** to `{tz}`.", ephemeral=True)
        await interaction.edit_original_response(view=self.parent_view)

class TeamModifyModalLoop(discord.ui.Modal):
    def __init__(self, teams, team_idx, field, current_value):
        super().__init__(title=f"Modify {field.replace('_',' ').title()}")
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.input = discord.ui.TextInput(label=f"New value for {field.replace('_',' ').title()}", default=str(current_value), required=True)
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        new_value = self.input.value
        team = self.teams[self.team_idx]
        team[self.field] = new_value
        guild_id = str(interaction.guild_id)
        servers = ReadJSON("data/servers.json")
        current_server = servers.get(guild_id, {})
        current_server["teams"] = self.teams
        servers[guild_id] = current_server
        WriteJSON(servers, "data/servers.json")
        await log_to_discord(interaction.client, guild_id, f"Updated {self.field} for team '{team['team_name']}' to '{new_value}' by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(f"Updated **{self.field.replace('_',' ').title()}** to `{new_value}` for team **{team['team_name']}**.", ephemeral=True)

# ---------- LIST TEAMS ----------

class TeamListView(discord.ui.View):
    def __init__(self, teams, interaction, per_page=5):
        super().__init__(timeout=120)
        self.teams = teams
        self.interaction = interaction
        self.per_page = max(1, min(per_page, 25))
        self.page = 0
        self.max_page = max(0, math.ceil(len(teams) / self.per_page) - 1)

        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.stop_button = discord.ui.Button(label="Stop", style=discord.ButtonStyle.danger)

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.stop_button.callback = self.stop_view

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.stop_button)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.max_page

    async def prev_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.page < self.max_page:
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def stop_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Command Done", embed=None, view=None)

    def get_embed(self):
        embed = discord.Embed(
            title="Teams in this Server",
            description=f"Total Teams: {len(self.teams)}",
            color=discord.Color.blue()
        )
        start = self.page * self.per_page
        end = start + self.per_page
        for team in self.teams[start:end]:
            team_captain = self.interaction.guild.get_member(team.get("team_captain_id"))
            team_role = self.interaction.guild.get_role(team.get("team_role_id"))
            team_schedule_channel = self.interaction.guild.get_channel(team["team_schedule_channel"])
            embed.add_field(
                name=team["team_name"],
                value=(
                    f"Game: {team['game']}\n"
                    f"Team Captain: {team_captain.mention if team_captain else 'User not found'}\n"
                    f"Team Role: {team_role.mention if team_role else 'Role not found'}\n"
                    f"Schedule Channel: {team_schedule_channel.mention if team_schedule_channel else 'Channel not found'}\n"
                    f"Timezone: {team['timezone']}\n"
                    f"Created At: {team['created_at']}"
                ),
                inline=False
            )
        embed.set_footer(text=f"Page {self.page + 1} of {self.max_page + 1}")
        return embed

# ---------- COG ----------

class TeamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def timezone_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=tz, value=tz)
            for tz in MAJOR_TIMEZONES
            if current.lower() in tz.lower()
        ][:25]

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
        timezone: str
    ):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(self.bot, guild_id, f"Unauthorized create_team attempt by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return
        current_server = ReadJSON("data/servers.json").get(guild_id, {})
        if not current_server.get("SetupComplete", False):
            await log_to_discord(self.bot, guild_id, f"create_team failed: bot not setup by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("Bot not setup yet.", ephemeral=True)
            return
        teams = current_server.get("teams", [])
        team_data = {
            "team_name": team_name,
            "game": game,
            "team_captain_id": team_captain.id,
            "team_role_id": team_role.id,
            "team_schedule_channel": team_schedule_channel.id,
            "timezone": timezone,
            "created_at": str(interaction.created_at)
        }
        teams.append(team_data)
        current_server["teams"] = teams
        all_servers = ReadJSON("data/servers.json")
        all_servers[guild_id] = current_server
        WriteJSON(all_servers, "data/servers.json")
        await log_to_discord(self.bot, guild_id, f"Team '{team_name}' created for '{game}' by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(
            f"Team '{team_name}' created for '{game}'. Captain: {team_captain.mention}, Role: {team_role.mention}, Channel: {team_schedule_channel.mention}, Timezone: {timezone}",
            ephemeral=True
        )

    @app_commands.command(name="list_teams", description="List all teams in this server.")
    @app_commands.describe(per_page="Number of teams per page (default 5, max 25)")
    async def list_teams(self, interaction: discord.Interaction, per_page: int = 5):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(self.bot, guild_id, f"Unauthorized list_teams attempt by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("You do not have permission.", ephemeral=True)
            return
        current_server = ReadJSON("data/servers.json").get(guild_id, {})
        if not current_server.get("SetupComplete", False):
            await log_to_discord(self.bot, guild_id, f"list_teams failed: bot not setup by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("Bot not setup yet.", ephemeral=True)
            return
        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(self.bot, guild_id, f"list_teams: no teams found by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("No teams.", ephemeral=True)
            return
        view = TeamListView(teams, interaction, per_page=per_page)
        await log_to_discord(self.bot, guild_id, f"Teams listed by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)

    @app_commands.command(name="delete_team", description="Delete a team from this server.")
    async def delete_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(self.bot, guild_id, f"Unauthorized delete_team attempt by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        current_server = ReadJSON("data/servers.json").get(guild_id, {})
        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(self.bot, guild_id, f"delete_team: no teams to delete by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("No teams to delete.", ephemeral=True)
            return
        view = TeamDeleteView(teams)
        await log_to_discord(self.bot, guild_id, f"Team delete view sent by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message("Select a team to delete:", view=view, ephemeral=True)

    @app_commands.command(name="modify_team", description="Modify a team's details.")
    async def modify_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        user_roles = [role.id for role in interaction.user.roles]
        if not CheckIfAdminRole(user_roles, guild_id):
            await log_to_discord(self.bot, guild_id, f"Unauthorized modify_team attempt by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("No permission.", ephemeral=True)
            return
        current_server = ReadJSON("data/servers.json").get(guild_id, {})
        teams = current_server.get("teams", [])
        if not teams:
            await log_to_discord(self.bot, guild_id, f"modify_team: no teams found by {interaction.user} ({interaction.user.id})")
            await interaction.response.send_message("No teams found.", ephemeral=True)
            return
        view = TeamModifyView(teams, interaction.guild, 0)
        await log_to_discord(self.bot, guild_id, f"Team modify view sent by {interaction.user} ({interaction.user.id})")
        await interaction.response.send_message(content=f"Modify team: **{teams[0]['team_name']}**", view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(TeamCog(bot))
