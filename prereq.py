import os
import json

def EnsurePreReq():
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/events", exist_ok=True)  # Ensure events folder exists

    # Ensure servers.json exists
    servers_path = "data/servers.json"
    if not os.path.exists(servers_path):
        with open(servers_path, "w") as f:
            json.dump({}, f, indent=4)

    # Ensure day availability state exists
    day_availability_path = "data/day_availability.json"
    if not os.path.exists(day_availability_path):
        with open(day_availability_path, "w") as f:
            json.dump({}, f, indent=4)




