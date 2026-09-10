import json
import os

from utils.server_store import initialize_storage
from utils.status_store import ensure_status_files


def EnsurePreReq():
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/events", exist_ok=True)  # Ensure events folder exists

    # Ensure servers.json exists
    servers_path = "data/servers.json"
    if not os.path.exists(servers_path):
        with open(servers_path, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
        print("Created data/servers.json backup file.")

    initialize_storage(logger=print)
    ensure_status_files()
    print("Storage and status prerequisites are ready.")


if __name__ == "__main__":
    EnsurePreReq()



