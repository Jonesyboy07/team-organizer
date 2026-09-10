import os

VERSION_FILE = "data/version.txt"


def read_version() -> str:
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as handle:
            return handle.read().strip() or "Unknown"
    except OSError:
        return "Unknown"


def write_version(version: str) -> str:
    normalized = version.strip()
    if not normalized:
        raise ValueError("Version cannot be empty.")
    parent = os.path.dirname(VERSION_FILE)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(VERSION_FILE, "w", encoding="utf-8") as handle:
        handle.write(normalized)
    return normalized
