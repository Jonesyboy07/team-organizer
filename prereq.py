import json
import os


def EnsurePreReq():
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/events", exist_ok=True)  # Ensure events folder exists

    # Ensure servers.json exists
    servers_path = "data/servers.json"
    if not os.path.exists(servers_path):
        with open(servers_path, "w") as f:
            json.dump({}, f, indent=4)




