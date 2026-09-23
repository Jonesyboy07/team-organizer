from pathlib import Path

from utils.server_store import DB_FILE, SERVERS_FILE, read_servers

ROOT_DIR = Path(__file__).resolve().parents[2]
FILE_BACKED_SOURCES = [
    ("Command help cache", "data/commands.json", "JSON", "Generated slash-command help content"),
    ("Default statuses", "data/default_statuses.json", "JSON", "Tracked rotating status defaults"),
    ("Custom statuses", "data/custom_statuses.json", "JSON", "Owner-added rotating statuses"),
    ("Event state", "data/events", "Directory", "Per-guild RSVP event data"),
    ("Schedule state", "data/schedule_events", "Directory", "Weekly scheduling state by guild"),
    ("Scrim requests", "data/scrim_requests", "Directory", "Scrim request state by guild"),
    ("Games catalog", "data/games.json", "JSON", "Game, region, and suggestion data"),
    ("Stats cache", "data/stats_hidden.json", "JSON", "Cached stats output"),
    ("Bot version", "data/version.txt", "Text", "Displayed bot version string"),
    ("Update message", "data/update.txt", "Text", "Owner update message content"),
]


def _source_entry(name: str, relative_path: str, kind: str, description: str, repo_root: Path) -> dict:
    return {
        "name": name,
        "path": relative_path,
        "kind": kind,
        "description": description,
        "exists": (repo_root / relative_path).exists(),
    }


def get_storage_overview(repo_root: Path | None = None, server_data_loader=read_servers) -> dict:
    repo_root = repo_root or ROOT_DIR
    servers = server_data_loader()
    team_count = sum(
        len(server_data.get("teams", []))
        for server_data in servers.values()
        if isinstance(server_data, dict)
    )
    sources = [
        _source_entry(
            "Server configuration",
            DB_FILE,
            "SQLite",
            "Primary dashboard-backed server configuration store",
            repo_root,
        ),
        _source_entry(
            "Server configuration backup",
            SERVERS_FILE,
            "JSON",
            "Legacy backup kept after the SQLite migration",
            repo_root,
        ),
    ]
    sources.extend(
        _source_entry(name, relative_path, kind, description, repo_root)
        for name, relative_path, kind, description in FILE_BACKED_SOURCES
    )

    return {
        "summary": {
            "server_count": len(servers),
            "team_count": team_count,
        },
        "sources": sources,
    }


def build_dashboard_context(
    website_port: int = 9090,
    discord_oauth_ready: bool = False,
    repo_root: Path | None = None,
    server_data_loader=read_servers,
) -> dict:
    return {
        "storage": get_storage_overview(repo_root=repo_root, server_data_loader=server_data_loader),
        "outline": {
            "backend": "Flask routes and shared Python storage helpers",
            "frontend": "Jinja page shell with a React mount point for future interactive widgets",
            "auth": "Discord OAuth2 login flow" if discord_oauth_ready else "Discord OAuth2 env configured later",
            "port": website_port,
        },
        "next_steps": [
            "Wire Discord OAuth callbacks into Flask routes",
            "Move dashboard-managed writes into shared storage helpers",
            "Replace the placeholder React mount with authenticated widgets",
        ],
    }
