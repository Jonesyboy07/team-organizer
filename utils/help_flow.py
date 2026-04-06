import discord


class HelpSectionRow(discord.ui.ActionRow):
    def __init__(self, parent_view: "HelpLayoutView"):
        super().__init__()
        self.parent_view = parent_view

        options = [discord.SelectOption(label="All", value="all", description="Show all commands")]
        for section in self.parent_view.sections:
            options.append(
                discord.SelectOption(
                    label=section["name"],
                    value=section["name"],
                    description=f"Show {section['name']} commands",
                )
            )

        self.section_select = discord.ui.Select(
            placeholder="Choose a section...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.section_select.callback = self.on_select
        self.add_item(self.section_select)

    async def on_select(self, interaction: discord.Interaction):
        self.parent_view.selected_section = self.section_select.values[0]
        self.parent_view.page = 0
        self.parent_view.refresh_content()
        await interaction.response.edit_message(view=self.parent_view)


class HelpControlsRow(discord.ui.ActionRow):
    def __init__(self, parent_view: "HelpLayoutView"):
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


class HelpLayoutView(discord.ui.LayoutView):
    def __init__(self, sections, per_page=5):
        super().__init__(timeout=120)
        self.sections = sections
        self.per_page = per_page
        self.selected_section = "all"
        self.page = 0
        self.max_page = 0
        self.closed = False

        self.header = discord.ui.TextDisplay("")
        self.body = discord.ui.TextDisplay("")

        container = discord.ui.Container(accent_color=discord.Color.blue())
        container.add_item(self.header)
        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small, divider=True))
        container.add_item(self.body)

        self.controls_row = HelpControlsRow(self)
        self.section_row = HelpSectionRow(self)

        container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.large, divider=False))
        container.add_item(self.controls_row)
        container.add_item(self.section_row)
        self.add_item(container)

        self.refresh_content()

    def get_commands(self):
        if self.selected_section == "all":
            combined = []
            for section in self.sections:
                combined.extend(section.get("commands", []))
            return combined

        for section in self.sections:
            if section.get("name") == self.selected_section:
                return section.get("commands", [])
        return []

    def refresh_content(self):
        if self.closed:
            self.header.content = "## Help"
            self.body.content = "This help session is closed. Run /help again to open a new one."
            self.controls_row.prev_button.disabled = True
            self.controls_row.next_button.disabled = True
            self.controls_row.stop_button.disabled = True
            self.section_row.section_select.disabled = True
            return

        commands = self.get_commands()
        self.max_page = max(0, (len(commands) - 1) // self.per_page)
        self.page = min(self.page, self.max_page)

        start = self.page * self.per_page
        end = start + self.per_page
        page_commands = commands[start:end]

        lines = []
        for command in page_commands:
            admin_required = "Requires Admin" if command.get("admin_required", False) else "No Admin Required"
            lines.append(
                f"### /{command['name']}\n"
                f"-# {command['description']}\n"
                f"Usage: {command['usage']}\n"
                f"Permission: {admin_required}"
            )

        body_text = "\n\n".join(lines) if lines else "No commands found in this section."
        self.header.content = (
            f"## Help\n"
            f"-# Section: {self.selected_section.capitalize()} | Page {self.page + 1}/{self.max_page + 1}"
        )
        self.body.content = body_text

        self.controls_row.prev_button.disabled = self.page == 0
        self.controls_row.next_button.disabled = self.page >= self.max_page
