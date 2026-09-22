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
