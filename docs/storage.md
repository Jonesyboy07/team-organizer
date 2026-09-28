# Storage

Server configuration now lives in `data/storage.db`.

## Migration

- On first startup, the bot creates the SQLite tables it needs.
- If `data/servers.json` exists, its contents are migrated into `data/storage.db`.
- A metadata flag inside the database records that the migration has already run.
- `data/servers.json` is kept as a backup and is not deleted or renamed.

## What stays outside SQLite

- `data/commands.json` for generated slash-command help content
- `data/default_statuses.json` for tracked rotating status defaults
- `data/custom_statuses.json` for owner-added rotating statuses
- `data/events/` for per-guild RSVP event data
- `data/schedule_events/` for weekly scheduling event state by guild
- `data/scrim_requests/` for scrim request state by guild
- `data/games.json` for game, region, and suggestion data
- `data/stats_hidden.json` for cached stats output
- `data/version.txt` for the bot version string
- `data/update.txt` for owner update-message content

## Remaining storage work

The website now stores its sessions, bot heartbeat, and action queue in `data/storage.db`. Server configuration remains JSON serialized in the `servers` table; events, schedules, stats, version, and update notes remain in their existing files. Website writes are limited to queued actions and are revalidated by the bot before changing server records or sending Discord messages.

Longer-term storage work remains:

- add formal schema versions and migrations for future SQLite changes
- review same-guild concurrent team edits and backup/restore procedures
- add broader migration and bot/website concurrency tests as those shared storage paths expand

## Website integration

The website in `website/` uses a React/Vite frontend and Flask API. The bot and website share `data/storage.db`; a SQLite action queue lets Flask submit requests while the bot performs Discord operations and checks permissions again. OAuth sessions and runtime heartbeats are also stored in this database. OAuth credentials are encrypted using the stable `WEBSITE_SECRET_KEY`.

The dashboard is private by default. Logged-out visitors can only see the sign-in screen and legal pages. After Discord OAuth, users see only guilds they own/administer or teams they captain; the tracked-user statistic is visible only to the configured bot owner. Sessions roll forward while active and expire after 90 days of inactivity. Discord refresh credentials renew the login and update guild membership and permissions.

Discord OAuth and website variables use the existing project `.env` file:

- `DISCORD_OAUTH_CLIENT_ID`
- `DISCORD_OAUTH_CLIENT_SECRET`
- `WEBSITE_BASE_URL` (canonical website origin; the OAuth callback path is derived automatically)
- `WEBSITE_HOST`
- `WEBSITE_PORT`
- `WEBSITE_SECRET_KEY` (stable across restarts; used to sign sessions and encrypt stored OAuth credentials)

Build the frontend with `website/scripts/build-frontend.bat` (Windows) or `sh website/scripts/build-frontend.sh` (Linux/macOS). The bot must be running to drain the action queue. Internet-facing deployments require HTTPS and a TLS reverse proxy; see `website/README.md`.
