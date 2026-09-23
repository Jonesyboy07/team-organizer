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

## Dashboard prep checklist

No runtime storage changes have been made yet. Before adding a web dashboard that reads or updates `data/storage.db`, we should:

- document the current SQLite schema and the JSON/text files that still hold bot state
- decide which dashboard-managed data must move into SQLite instead of staying split across JSON files and folders
- add schema versioning and explicit migrations for future database changes
- define which records the dashboard may create, edit, or delete and validate those write paths in one shared storage layer
- standardize IDs, required fields, and timestamps so bot code and dashboard code read the same shapes
- review concurrent write safety so bot actions and dashboard actions cannot overwrite each other
- decide how backups, rollback, and recovery should work for both the database and any remaining file-based data
- add tests around storage migrations and dashboard-facing CRUD flows once the data model is finalized

## Current website foundation

The starter website scaffold now lives in `website/` and currently does three things:

- runs a Flask app on port `9090` by default
- renders a Jinja dashboard shell with a React mount point placeholder for future client-side widgets
- summarizes the current storage split so the dashboard foundation reflects the same database/file-backed data described above

Discord OAuth and website variables use the existing project `.env` file:

- `DISCORD_OAUTH_CLIENT_ID`
- `DISCORD_OAUTH_CLIENT_SECRET`
- `DISCORD_OAUTH_REDIRECT_URI` (optional override; defaults to `WEBSITE_URL_SCHEME` + `WEBSITE_HOST` + `WEBSITE_PORT`)
- `WEBSITE_HOST`
- `WEBSITE_PORT`
- `WEBSITE_URL_SCHEME`
- `WEBSITE_SECRET_KEY`
