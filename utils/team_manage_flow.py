import math
import discord

from utils.funcs import log_to_discord
from utils.constants import MAJOR_TIMEZONES
from utils.server_store import save_teams
from utils.command_helpers import CommandResponse


def persist_teams(guild_id: str, teams: list):
    save_teams(guild_id, teams)


class TeamDeleteDropdown(discord.ui.Select):
    def __init__(self, teams):
        options = [discord.SelectOption(label=team["team_name"], value=str(idx)) for idx, team in enumerate(teams)]
        super().__init__(placeholder="Select a team to delete...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: TeamDeleteView = self.view
        idx = int(self.values[0])
        team = view.teams[idx]
        guild_id = str(interaction.guild_id)
        teams = self.view.teams
        teams.pop(idx)
        persist_teams(guild_id, teams)
        await log_to_discord(
            interaction.client,
            guild_id,
            f"Team '{team['team_name']}' deleted by {interaction.user} ({interaction.user.id})",
        )
        await interaction.response.edit_message(content=f"✅ Team **{team['team_name']}** has been deleted.", view=None, embed=None)


class TeamDeleteView(discord.ui.View):
    def __init__(self, teams):
        super().__init__(timeout=60)
        self.teams = teams
        self.add_item(TeamDeleteDropdown(teams))


class PaginatedSelectView(discord.ui.View):
    """Base class for paginated selects (members, roles, channels)."""

    def __init__(self, items, label_fn, select_cls, teams, team_idx, field, parent_view, per_page=25):
        super().__init__(timeout=180)
        self.items = items
        self.label_fn = label_fn
        self.select_cls = select_cls
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        self.page = 0
        self.per_page = per_page
        self.max_page = max(0, math.ceil(len(items) / per_page) - 1)

        self.prev_btn = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.prev_btn.callback = self.prev_page
        self.next_btn.callback = self.next_page

        self.update_dropdown()

    def update_dropdown(self):
        start = self.page * self.per_page
        end = start + self.per_page
        opts = [discord.SelectOption(label=self.label_fn(x), value=str(x.id)) for x in self.items[start:end]]
        self.clear_items()
        dropdown = self.select_cls(self.teams, self.team_idx, self.field, opts, self.parent_view)
        self.add_item(dropdown)
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)

    async def prev_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_dropdown()
            await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.page < self.max_page:
            self.page += 1
            self.update_dropdown()
            await interaction.response.edit_message(view=self)


class MemberSelectPaginated(PaginatedSelectView):
    def __init__(self, teams, team_idx, field, guild, parent_view):
        super().__init__(
            items=guild.members,
            label_fn=lambda m: m.display_name,
            select_cls=MemberSelectLoop,
            teams=teams,
            team_idx=team_idx,
            field=field,
            parent_view=parent_view,
        )


class RoleSelectPaginated(PaginatedSelectView):
    def __init__(self, teams, team_idx, field, guild, parent_view):
        super().__init__(
            items=guild.roles,
            label_fn=lambda r: r.name,
            select_cls=RoleSelectLoop,
            teams=teams,
            team_idx=team_idx,
            field=field,
            parent_view=parent_view,
        )


class ChannelSelectPaginated(PaginatedSelectView):
    def __init__(self, teams, team_idx, field, guild, parent_view):
        super().__init__(
            items=guild.text_channels,
            label_fn=lambda c: c.name,
            select_cls=ChannelSelectLoop,
            teams=teams,
            team_idx=team_idx,
            field=field,
            parent_view=parent_view,
        )


class TeamModifyView(discord.ui.View):
    """Main modify view for a specific team with looping."""

    def __init__(self, teams, guild: discord.Guild, team_idx: int, root_view=None):
        super().__init__(timeout=180)
        self.teams = teams
        self.guild = guild
        self.team_idx = team_idx

        self.root_view = root_view if root_view else self

        self.field_dropdown = TeamFieldDropdownLoop(teams, team_idx, guild, self)
        self.add_item(self.field_dropdown)

        close_btn = discord.ui.Button(label="Close", style=discord.ButtonStyle.danger)
        close_btn.callback = self.close_view
        self.add_item(close_btn)

        home_btn = discord.ui.Button(label="Home", style=discord.ButtonStyle.primary)
        home_btn.callback = self.go_home
        self.add_item(home_btn)

        team_select_btn = discord.ui.Button(label="Change Team", style=discord.ButtonStyle.secondary)
        team_select_btn.callback = self.change_team
        self.add_item(team_select_btn)

    async def close_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="✅ Modification session closed.", view=None)
        self.stop()

    async def go_home(self, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content=f"Modify team: **{self.teams[self.team_idx]['team_name']}**", view=self.root_view
        )

    async def change_team(self, interaction: discord.Interaction):
        options = [discord.SelectOption(label=t["team_name"], value=str(i)) for i, t in enumerate(self.teams)]

        class TeamSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(
                    placeholder="Select a team to modify...", min_values=1, max_values=1, options=options
                )

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
        persist_teams(guild_id, self.teams)
        member = interaction.guild.get_member(new_member_id)
        await log_to_discord(
            interaction.client,
            guild_id,
            f"Updated {self.field} for team '{team['team_name']}' to member '{member.display_name if member else new_member_id}' by {interaction.user} ({interaction.user.id})",
        )
        await CommandResponse.success(
            interaction,
            f"Updated **Team Captain** to **{member.mention if member else new_member_id}** for team **{team['team_name']}**.",
        )
        await interaction.edit_original_response(view=self.parent_view)


class RoleSelectLoop(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        super().__init__(placeholder=f"Select new {field.replace('_', ' ').title()}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        new_role_id = int(self.values[0])
        team = self.teams[self.team_idx]
        team[self.field] = new_role_id
        guild_id = str(interaction.guild_id)
        persist_teams(guild_id, self.teams)
        role = interaction.guild.get_role(new_role_id)
        await log_to_discord(
            interaction.client,
            guild_id,
            f"Updated {self.field} for team '{team['team_name']}' to role '{role.name if role else new_role_id}' by {interaction.user} ({interaction.user.id})",
        )
        await CommandResponse.success(
            interaction,
            f"Updated **Team Role** to **{role.mention if role else new_role_id}** for team **{team['team_name']}**.",
        )
        await interaction.edit_original_response(view=self.parent_view)


class ChannelSelectLoop(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        super().__init__(placeholder=f"Select new {field.replace('_', ' ').title()}...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        new_channel_id = int(self.values[0])
        team = self.teams[self.team_idx]
        team[self.field] = new_channel_id
        guild_id = str(interaction.guild_id)
        persist_teams(guild_id, self.teams)
        channel = interaction.guild.get_channel(new_channel_id)
        channel_name = channel.name if channel else str(new_channel_id)
        await log_to_discord(
            interaction.client,
            guild_id,
            f"Updated {self.field} for team '{team['team_name']}' to channel '{channel_name}' by {interaction.user} ({interaction.user.id})",
        )
        await CommandResponse.success(
            interaction,
            f"Updated **{self.field.replace('_', ' ').title()}** to **{channel_name}** for team **{team['team_name']}**.",
        )
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
            discord.SelectOption(label="Match Request Channel", value="team_request_channel"),
            discord.SelectOption(label="Timezone", value="timezone"),
        ]
        super().__init__(placeholder="Select a field to modify...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        field = self.values[0]
        team = self.teams[self.team_idx]

        if field == "team_captain_id":
            view = MemberSelectPaginated(self.teams, self.team_idx, field, self.guild, self.parent_view)
            await interaction.response.edit_message(content=f"Select new Team Captain for **{team['team_name']}**:", view=view)
        elif field == "team_role_id":
            view = RoleSelectPaginated(self.teams, self.team_idx, field, self.guild, self.parent_view)
            await interaction.response.edit_message(content=f"Select new Team Role for **{team['team_name']}**:", view=view)
        elif field in {"team_schedule_channel", "team_request_channel"}:
            view = ChannelSelectPaginated(self.teams, self.team_idx, field, self.guild, self.parent_view)
            field_name = "Schedule Channel" if field == "team_schedule_channel" else "Match Request Channel"
            await interaction.response.edit_message(content=f"Select new {field_name} for **{team['team_name']}**:", view=view)
        elif field == "timezone":
            tz_select = TimezoneSelectPaginated(self.teams, self.team_idx, field, self.parent_view)
            await interaction.response.edit_message(content=f"Select timezone for **{team['team_name']}**:", view=tz_select)
        else:
            await interaction.response.send_modal(TeamModifyModalLoop(self.teams, self.team_idx, field, team.get(field, "")))


class TimezoneSelectPaginated(discord.ui.View):
    """Shows paginated dropdown for timezones."""

    def __init__(self, teams, team_idx, field, parent_view):
        super().__init__(timeout=180)
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        self.page = 0
        self.per_page = 10
        self.max_page = max(0, math.ceil(len(MAJOR_TIMEZONES) / self.per_page) - 1)

        self.prev_btn = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self.next_btn = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.prev_btn.callback = self.prev_page
        self.next_btn.callback = self.next_page

        self.update_dropdown()

    def update_dropdown(self):
        start = self.page * self.per_page
        end = start + self.per_page
        tz_options = [discord.SelectOption(label=tz, value=tz) for tz in MAJOR_TIMEZONES[start:end]]
        self.clear_items()
        self.add_item(TimezoneSelectDropdown(self.teams, self.team_idx, self.field, tz_options, self.parent_view))
        self.add_item(self.prev_btn)
        self.add_item(self.next_btn)

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


class TimezoneSelectDropdown(discord.ui.Select):
    def __init__(self, teams, team_idx, field, options, parent_view):
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.parent_view = parent_view
        super().__init__(placeholder="Select a timezone...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        tz = self.values[0]
        team = self.teams[self.team_idx]
        team[self.field] = tz
        guild_id = str(interaction.guild_id)
        persist_teams(guild_id, self.teams)
        await log_to_discord(
            interaction.client,
            guild_id,
            f"Updated timezone for team '{team['team_name']}' to '{tz}' by {interaction.user} ({interaction.user.id})",
        )
        await CommandResponse.success(interaction, f"Updated timezone for **{team['team_name']}** to `{tz}`.")
        await interaction.edit_original_response(view=self.parent_view)


class TeamModifyModalLoop(discord.ui.Modal):
    def __init__(self, teams, team_idx, field, current_value):
        super().__init__(title=f"Modify {field.replace('_', ' ').title()}")
        self.teams = teams
        self.team_idx = team_idx
        self.field = field
        self.input = discord.ui.TextInput(
            label=f"New value for {field.replace('_', ' ').title()}", default=str(current_value), required=True
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        new_value = self.input.value
        team = self.teams[self.team_idx]
        team[self.field] = new_value
        guild_id = str(interaction.guild_id)
        persist_teams(guild_id, self.teams)
        await log_to_discord(
            interaction.client,
            guild_id,
            f"Updated {self.field} for team '{team['team_name']}' to '{new_value}' by {interaction.user} ({interaction.user.id})",
        )
        await CommandResponse.success(
            interaction,
            f"Updated **{self.field.replace('_', ' ').title()}** to `{new_value}` for team **{team['team_name']}**.",
        )


class TeamListControlsRow(discord.ui.ActionRow):
    def __init__(self, parent_view: "TeamListView"):
        super().__init__()
        self.parent_view = parent_view

        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self.stop_button = discord.ui.Button(label="Stop", style=discord.ButtonStyle.danger)

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.stop_button.callback = self.stop_view

        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.stop_button)

    async def prev_page(self, interaction: discord.Interaction):
        if self.parent_view.page > 0:
            self.parent_view.page -= 1
            self.parent_view.refresh_content()
            await interaction.response.edit_message(view=self.parent_view)
        else:
            await interaction.response.defer()

    async def next_page(self, interaction: discord.Interaction):
        if self.parent_view.page < self.parent_view.max_page:
            self.parent_view.page += 1
            self.parent_view.refresh_content()
            await interaction.response.edit_message(view=self.parent_view)
        else:
            await interaction.response.defer()

    async def stop_view(self, interaction: discord.Interaction):
        self.parent_view.closed = True
        self.parent_view.refresh_content()
        await interaction.response.edit_message(view=self.parent_view)


class TeamListView(discord.ui.LayoutView):
    def __init__(self, teams, interaction, per_page=5):
        super().__init__(timeout=120)
        self.teams = teams
        self.interaction = interaction
        self.per_page = max(1, min(per_page, 25))
        self.page = 0
        self.max_page = max(0, math.ceil(len(teams) / self.per_page) - 1)
        self.closed = False
        self.header = discord.ui.TextDisplay("")
        self.body = discord.ui.TextDisplay("")

        container = discord.ui.Container(accent_color=discord.Color.blue())
        container.add_item(self.header)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, divider=True))
        container.add_item(self.body)

        self.controls = TeamListControlsRow(self)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large, divider=False))
        container.add_item(self.controls)
        self.add_item(container)

        self.refresh_content()

    def refresh_content(self):
        if self.closed:
            self.header.content = "## Teams"
            self.body.content = "Team listing session closed. Run /list_teams to view again."
            self.controls.prev_button.disabled = True
            self.controls.next_button.disabled = True
            self.controls.stop_button.disabled = True
            return

        start = self.page * self.per_page
        end = start + self.per_page
        lines = []
        for team in self.teams[start:end]:
            team_captain = self.interaction.guild.get_member(team.get("team_captain_id"))
            team_role = self.interaction.guild.get_role(team.get("team_role_id"))
            schedule_channel_id = team.get("team_schedule_channel")
            request_channel_id = team.get("team_request_channel")
            schedule_channel = self.interaction.guild.get_channel(schedule_channel_id) if schedule_channel_id else None
            request_channel = self.interaction.guild.get_channel(request_channel_id) if request_channel_id else None
            lines.append(
                f"### {team['team_name']}\n"
                f"Game: {team.get('game', 'Unknown')}\n"
                f"Captain: {team_captain.mention if team_captain else 'User not found'}\n"
                f"Role: {team_role.mention if team_role else 'Role not found'}\n"
                f"Schedule Channel: {schedule_channel.mention if schedule_channel else 'Channel not found'}\n"
                f"Match Request Channel: {request_channel.mention if request_channel else 'Channel not found'}\n"
                f"Timezone: {team.get('timezone', 'UTC')}\n"
                f"Created At: {team.get('created_at', 'Unknown')}"
            )

        self.header.content = f"## Teams in this Server\n-# Total: {len(self.teams)} | Page {self.page + 1}/{self.max_page + 1}"
        self.body.content = "\n\n".join(lines) if lines else "No teams found."

        self.controls.prev_button.disabled = self.page == 0
        self.controls.next_button.disabled = self.page >= self.max_page
