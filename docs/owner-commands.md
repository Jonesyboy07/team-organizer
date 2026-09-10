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
- `!a_server_count` — list how many servers the bot is currently in
- `!a_servers` — list servers in `name:id:teams:users` format
- `!a_team_count` — list total teams across all tracked servers
- `!a_server_details <server_id>` — list all team names stored for a server
- `!a_team_blacklist <server_id>` — prevent a server from creating new teams
- `!a_ban_server <server_id>` — ban a server and make the bot leave it

## Rotating Status Variables

Statuses can include:

- `{users}`
- `{servers}`
- `{total_teams}`
