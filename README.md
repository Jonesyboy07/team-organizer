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

4. Initialize data files.

   Windows:
   py prereq.py

   Linux or macOS:
   python prereq.py

5. Start the bot.

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

Owner-only text command:
- update (prefix command, defaults to !update unless PREFIX is changed)

## Data Files

- data/servers.json stores per-server config, roles, channels, and teams.
- data/events stores RSVP event state by guild.
- data/commands.json powers help content.

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