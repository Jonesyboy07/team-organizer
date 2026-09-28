# Game Schedule Bot

A Discord bot for running team scheduling workflows with cleaner command UX and Component V2 cards.

## What This Bot Does

- Server setup in one flow
- Team management for multiple teams per server
- Weekly scheduling prompts
- Event RSVP cards with timezone-aware times
- Match request workflow between teams
- Built-in quickstart and help commands

## Fast Start (5 Minutes)

1. Clone the repository.

   Windows:
   git clone https://github.com/Jonesyboy07/team-organizer.git

   Linux or macOS:
   git clone https://github.com/Jonesyboy07/team-organizer.git

2. Install dependencies.

   Windows:
   py -m pip install -r requirements.txt

   Linux or macOS:
   python -m pip install -r requirements.txt

3. Create a .env file in the project root.

   Required values:
   DISCORD_TOKEN=your_bot_token
   DISCORD_CLIENT_ID=your_application_id

   Optional values:
   PREFIX=!
   OWNER_ID=your_discord_user_id

   Set the bot version in data/version.txt. This value is shown by /version.

4. Initialize data files.

   Windows:
   py prereq.py

   Linux or macOS:
   python prereq.py

5. Optional owner setup.

   - Set `OWNER_ID` in `.env` to unlock owner-only prefix commands.
   - Use `!a_help` after startup to view the owner command list.
   - Default rotating statuses are tracked in `data/default_statuses.json`.
   - Custom rotating statuses are written to `data/custom_statuses.json`, which is gitignored.

6. Start the bot.

   Windows:
   py main.py

   Linux or macOS:
   python main.py

## Walkthrough: Server Admin First Setup

Use this flow on a fresh server.

1. Run /setup.

   You will provide:
   - Command channel
   - Admin role
   - Update logs channel
   - Bot logs channel

2. Verify config.

   Run:
   - /listbotchannels
   - /listadminroles

3. Create your first team.

   Run /create_team and set:
   - Team name
   - Game
   - Team captain
   - Team role
   - Schedule channel
   - Match request channel
   - Timezone

4. Test scheduling.

   Run /send_schedule and choose a team.

5. Test events.

   Run /event with:
   - team_name
   - date (YYYY-MM-DD)
   - time (hhmm in 24-hour format, example 1930)
   - event_name

## Walkthrough: Team Captain Weekly Flow

1. Run /my_teams to confirm your linked teams.
2. Run /send_schedule each week if you want a manual push.
3. Run /request_match to send match requests.
4. Run /event to create RSVP cards for scrims, officials, or practices.
5. Use /help or /quickstart when teammates need command guidance.

## Command Map

Setup and configuration:
- /setup
- /addbotchannel
- /removebotchannel
- /addadminrole
- /removeadminrole
- /listbotchannels
- /listadminroles
- /setbotlogchannel

Team and match operations:
- /my_teams
- /create_team
- /list_teams
- /modify_team
- /delete_team
- /request_match

Scheduling and events:
- /send_schedule
- /event

Help and utility:
- /quickstart
- /help
- /version
- /ping
- /info
- /invite
- /stats

Owner-only text commands:
- a_help
- uptime
- sync_commands
- refresh_help_docs
- set_version
- update
- status_list
- status_add
- status_remove
- status_refresh
- a_server_count
- a_servers
- a_team_count
- a_server_details
- a_team_blacklist
- a_ban_server

## Data Files

- data/storage.db is the live server config database.
- data/servers.json is preserved as a JSON backup and migration source.
- data/events stores RSVP event state by guild.
- data/commands.json powers help content.
- data/default_statuses.json stores tracked rotating status defaults.
- data/custom_statuses.json stores owner-added rotating statuses.

## Website Dashboard

- The dashboard lives under `website/` and uses a React/Vite frontend, Flask API, Discord OAuth, and a bot-consumed SQLite action queue.
- Logged-out visitors see only the sign-in screen and legal pages. Guild details require Discord sign-in and are limited to servers the user owns/administers or teams they captain. Personal tracked-user statistics are owner-only.
- Discord OAuth is configured through `.env` values: `DISCORD_OAUTH_CLIENT_ID` and `DISCORD_OAUTH_CLIENT_SECRET`.
- Set `WEBSITE_BASE_URL` once to the full website origin, such as `http://127.0.0.1:9090` locally or `https://dashboard.example.com` publicly. The Discord callback is derived as `/auth/discord/callback` from this base URL.
- The bot and website load the project's `.env` and share `data/storage.db`. The bot must be running to process team, scheduling, and activity actions.
- Sessions last 90 days while active. OAuth refresh credentials are encrypted in `data/storage.db`; set a stable `WEBSITE_SECRET_KEY` so sessions survive restarts. Generate one with `py -c "import secrets; print(secrets.token_urlsafe(48))"`.
- For internet-facing use, set `WEBSITE_BASE_URL` to the public HTTPS origin and put the site behind a TLS reverse proxy. Do not expose Flask's development server directly.
- The website defaults to port `9090`.

Build the frontend after changing its source:

- Windows: `website\scripts\build-frontend.bat`
- Linux or macOS: `sh website/scripts/build-frontend.sh`

Run locally with:

- Windows: `website\scripts\run-website.bat`
- Linux or macOS: `./website/scripts/run-website.sh`

For Windows production use, install `requirements.txt` and run `website\scripts\run-website-prod.bat` behind a TLS reverse proxy. The site serves generic terms and privacy pages at `/terms` and `/privacy`; review them for your deployment and legal context.

## Additional Documentation

- docs/storage.md
- docs/owner-commands.md
- website/README.md

## Troubleshooting

- Commands not appearing:
  - Ensure DISCORD_CLIENT_ID is correct.
  - Restart the bot and wait for command sync logs.

- Permission errors:
  - Confirm your role is in admin roles via /listadminroles.
  - Confirm you are a configured team captain where needed.

- Event or schedule channel errors:
  - Check team channels with /modify_team.

## Contributing

Pull requests and issues are welcome.

- Issues: https://github.com/Jonesyboy07/team-organizer/issues
- Support: https://ko-fi.com/jonesy_alr

## Credit

If you fork or reuse this project, keep credit to the original author.