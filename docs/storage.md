# Storage

Server configuration now lives in `data/storage.db`.

## Migration

- On first startup, the bot creates the SQLite tables it needs.
- If `data/servers.json` exists, its contents are migrated into `data/storage.db`.
- A metadata flag inside the database records that the migration has already run.
- `data/servers.json` is kept as a backup and is not deleted or renamed.

## What stays in JSON

- `data/commands.json` for generated slash-command help content
- `data/default_statuses.json` for tracked rotating status defaults
- `data/custom_statuses.json` for owner-added rotating statuses
- `data/events/` for per-guild RSVP event data
