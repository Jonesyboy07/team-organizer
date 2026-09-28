# Owner Commands

Set `OWNER_ID` in `.env` to enable owner-only prefix commands.

## Available Commands

- `!a_help` — show the owner command list
- `!uptime` — show when the bot started and its current uptime
- `!sync_commands` — sync slash commands to Discord
- `!refresh_help_docs` — rebuild `data/commands.json`
- `!set_version <value>` — update `data/version.txt`
- `!update [text]` — optionally save `text` to `data/update.txt`, then broadcast to configured update channels
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

## Website Owner Panel

After Discord sign-in, the account matching `OWNER_ID` also gets a separate Bot admin dashboard. It provides queued controls for version changes, saving/broadcasting update text, adding/enabling/disabling rotating statuses, slash-command sync, help-cache refresh, team-creation blacklist/unblock, and server ban/leave. Owner server inventory includes server names, IDs, member/team counts, setup state, and team names; these details are not returned to other dashboard accounts.

The website has an Overview, a persistent server list on the left, and a Bot admin view available only to the configured bot owner. Each server opens its own Teams & Activities or Server setup view. The website rechecks the owner ID in Flask and the bot queue worker before executing any global owner action. Server setup controls require Discord server-owner/administrator permission, including configuration of bot command channels, admin roles, update-log and bot-log channels, and marking setup complete. Admins in the configured game-suggestion server can manage its suggestion blacklist from that server's setup view.

High-impact actions that broadcast updates or ban/leave servers require a confirmation in the interface. The bot remains the final authority and action results appear in the dashboard queue.

## Rotating Status Variables

Statuses can include:

- `{users}`
- `{servers}`
- `{total_teams}`
