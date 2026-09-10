# Owner Commands

Set `OWNER_ID` in `.env` to enable owner-only prefix commands.

## Available Commands

- `!a_help` — show the owner command list
- `!uptime` — show when the bot started and its current uptime
- `!sync_commands` — sync slash commands to Discord
- `!refresh_help_docs` — rebuild `data/commands.json`
- `!set_version <value>` — update `data/version.txt`
- `!update` — broadcast `data/update.txt` to configured update channels
- `!status_list` — list default and custom rotating statuses
- `!status_add <text>` — add or re-enable a custom rotating status
- `!status_remove <exact text>` — disable a status without deleting it
- `!status_refresh` — immediately move to the next rotating status

## Rotating Status Variables

Statuses can include:

- `{users}`
- `{servers}`
- `{total_teams}`
