import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import Lock

from flask import Blueprint, current_app, jsonify, redirect, request, session, url_for

from utils.constants import MAJOR_TIMEZONES
from utils.game_service import SUGGESTION_GUILD_ID, get_blacklisted_suggesters, get_games, get_regions
from utils.server_store import get_banned_server_ids, read_servers
from utils.status_store import list_statuses
from utils.version_store import read_version
from utils.website_queue import enqueue_action, list_user_actions, read_runtime_snapshot
from website.utils.auth_store import create_session, delete_session, get_session, update_session

api = Blueprint("website", __name__)
DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTHORIZE = "https://discord.com/oauth2/authorize"
ADMINISTRATOR_PERMISSION = 1 << 3
SESSION_REFRESH_MARGIN = timedelta(minutes=2)
GUILD_SNAPSHOT_TTL = timedelta(minutes=15)
SESSION_REFRESH_LOCK = Lock()


def _discord_request(path: str, method: str = "GET", data: dict | None = None, token: str | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    headers = {"User-Agent": "TeamOrganizerDashboard/1.0"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{DISCORD_API}{path}", data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _identity() -> dict | None:
    session_id = session.get("website_session")
    identity = get_session(session_id)
    if identity is None:
        return None
    now = datetime.now(timezone.utc)
    expires = datetime.fromisoformat(identity["access_expires_at"])
    guilds_updated = datetime.fromisoformat(identity.get("guilds_updated_at", "1970-01-01T00:00:00+00:00"))
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if guilds_updated.tzinfo is None:
        guilds_updated = guilds_updated.replace(tzinfo=timezone.utc)
    if expires > now + SESSION_REFRESH_MARGIN and guilds_updated > now - GUILD_SNAPSHOT_TTL:
        return identity
    with SESSION_REFRESH_LOCK:
        identity = get_session(session_id)
        if identity is None:
            return None
        now = datetime.now(timezone.utc)
        expires = datetime.fromisoformat(identity["access_expires_at"])
        guilds_updated = datetime.fromisoformat(identity.get("guilds_updated_at", "1970-01-01T00:00:00+00:00"))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if guilds_updated.tzinfo is None:
            guilds_updated = guilds_updated.replace(tzinfo=timezone.utc)
        if expires > now + SESSION_REFRESH_MARGIN and guilds_updated > now - GUILD_SNAPSHOT_TTL:
            return identity
        try:
            if expires <= now + SESSION_REFRESH_MARGIN:
                tokens = _discord_request("/oauth2/token", "POST", {
                    "client_id": current_app.config["DISCORD_OAUTH_CLIENT_ID"],
                    "client_secret": current_app.config["DISCORD_OAUTH_CLIENT_SECRET"],
                    "grant_type": "refresh_token",
                    "refresh_token": identity["refresh_token"],
                })
                identity.update({
                    "access_token": tokens["access_token"],
                    "refresh_token": tokens["refresh_token"],
                    "access_expires_at": (now + timedelta(seconds=int(tokens.get("expires_in", 3600)))).isoformat(),
                })
                user = _discord_request("/users/@me", token=identity["access_token"])
                identity["user"] = {key: user.get(key) for key in ("id", "username", "global_name", "avatar")}
            identity["guilds"] = _discord_request("/users/@me/guilds", token=identity["access_token"])
            identity["guilds_updated_at"] = now.isoformat()
            update_session(session_id, identity)
            return identity
        except (urllib.error.URLError, KeyError, ValueError, TypeError) as exc:
            current_app.logger.warning("Discord session renewal failed: %s", exc)
            delete_session(session_id)
            session.clear()
            return None


def _login_required(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        identity = _identity()
        if identity is None:
            return jsonify(error="Sign in with Discord to continue."), 401
        request.website_identity = identity
        return handler(*args, **kwargs)
    return wrapped


def _guild_permissions(identity: dict) -> dict[str, dict]:
    return {str(guild.get("id")): guild for guild in identity.get("guilds", [])}


def _is_admin(guild: dict) -> bool:
    try:
        return bool(guild.get("owner") or int(guild.get("permissions", "0")) & ADMINISTRATOR_PERMISSION)
    except (TypeError, ValueError):
        return bool(guild.get("owner"))


def _is_bot_owner(identity: dict) -> bool:
    owner_id = os.getenv("OWNER_ID", "")
    return bool(owner_id and str(identity["user"]["id"]) == owner_id)


def _read_update_text() -> str:
    try:
        with open("data/update.txt", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def _authorized_guilds(identity: dict) -> list[dict]:
    servers = read_servers()
    allowed = []
    for guild_id, membership in _guild_permissions(identity).items():
        server = servers.get(guild_id, {})
        captain_teams = [
            team for team in server.get("teams", [])
            if str(team.get("team_captain_id", "")) == str(identity["user"]["id"])
        ]
        is_admin = _is_admin(membership)
        if not is_admin and not captain_teams:
            continue
        allowed.append({
            "id": guild_id,
            "name": membership.get("name", "Discord server"),
            "icon": membership.get("icon"),
            "owner": bool(membership.get("owner")),
            "can_manage": is_admin,
            "team_count": len(server.get("teams", [])) if is_admin else len(captain_teams),
            "setup_complete": bool(server.get("SetupComplete", False)),
        })
    return allowed


@api.get("/auth/discord/login")
def discord_login():
    if not current_app.config["DISCORD_OAUTH_CLIENT_ID"] or not current_app.config["DISCORD_OAUTH_CLIENT_SECRET"]:
        return "Discord login is not configured. Set the website OAuth variables in .env.", 503
    try:
        from cryptography.fernet import Fernet  # noqa: F401
    except ImportError:
        return "Website encryption is unavailable. Install the dependencies in requirements.txt.", 503
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    query = urllib.parse.urlencode({
        "client_id": current_app.config["DISCORD_OAUTH_CLIENT_ID"],
        "redirect_uri": current_app.config["DISCORD_OAUTH_REDIRECT_URI"],
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "consent",
    })
    return redirect(f"{DISCORD_AUTHORIZE}?{query}")


@api.get("/auth/discord/callback")
def discord_callback():
    if request.args.get("error"):
        return redirect(url_for("dashboard", auth_error="cancelled"))
    state = request.args.get("state", "")
    if not state or not secrets.compare_digest(state, session.pop("oauth_state", "")):
        return "Discord sign-in state could not be verified. Return to the dashboard and try again.", 400
    code = request.args.get("code", "")
    if not code:
        return "Discord did not return an authorization code.", 400
    try:
        tokens = _discord_request("/oauth2/token", "POST", {
            "client_id": current_app.config["DISCORD_OAUTH_CLIENT_ID"],
            "client_secret": current_app.config["DISCORD_OAUTH_CLIENT_SECRET"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": current_app.config["DISCORD_OAUTH_REDIRECT_URI"],
        })
        user = _discord_request("/users/@me", token=tokens["access_token"])
        guilds = _discord_request("/users/@me/guilds", token=tokens["access_token"])
        if not tokens.get("refresh_token"):
            raise ValueError("Discord did not return a refresh token.")
        safe_user = {key: user.get(key) for key in ("id", "username", "global_name", "avatar")}
        session_id, _ = create_session(safe_user, tokens, guilds)
    except (urllib.error.URLError, KeyError, ValueError, TypeError, ImportError) as exc:
        current_app.logger.warning("Discord OAuth failed: %s", exc)
        return "Discord sign-in failed. Return to the dashboard and try again.", 502
    session.clear()
    session["website_session"] = session_id
    session.permanent = True
    return redirect(url_for("dashboard"))


@api.post("/auth/logout")
@_login_required
def logout():
    identity = request.website_identity
    if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), identity.get("csrf_token", "")):
        return jsonify(error="Request could not be verified."), 403
    delete_session(session.pop("website_session", None))
    session.clear()
    return jsonify(ok=True)


@api.get("/api/session")
def session_status():
    identity = _identity()
    if identity is None:
        return jsonify(authenticated=False, login_url=url_for("website.discord_login"))
    return jsonify(
        authenticated=True,
        user={key: identity["user"].get(key) for key in ("id", "username", "global_name", "avatar")},
        csrf_token=identity["csrf_token"],
        owner=_is_bot_owner(identity),
    )


@api.get("/api/dashboard")
@_login_required
def dashboard_data():
    identity = request.website_identity
    guilds = _authorized_guilds(identity)
    is_owner = _is_bot_owner(identity)
    servers = read_servers()
    runtime = read_runtime_snapshot()
    heartbeat_at = datetime.fromisoformat(runtime["heartbeat_at"]) if runtime else None
    if heartbeat_at and heartbeat_at.tzinfo is None:
        heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
    bot_online = bool(heartbeat_at and (datetime.now(timezone.utc) - heartbeat_at) < timedelta(seconds=90))
    metrics = {
        "server_count": runtime["guild_count"] if is_owner and runtime else (len(servers) if is_owner else len(guilds)),
        "team_count": sum(len(value.get("teams", [])) for value in servers.values()) if is_owner else sum(item["team_count"] for item in guilds),
    }
    if is_owner:
        try:
            with open("data/stats_hidden.json", encoding="utf-8") as handle:
                metrics["tracked_users"] = int(json.load(handle).get("total_users", 0))
        except (OSError, ValueError, TypeError):
            metrics["tracked_users"] = None
    try:
        with open("data/update.txt", encoding="utf-8") as handle:
            recent_update = handle.read().strip()
    except OSError:
        recent_update = "No update has been posted yet."
    return jsonify(
        user=identity["user"],
        is_owner=is_owner,
        guilds=guilds,
        metrics=metrics,
        version=read_version(),
        recent_update=recent_update,
        bot_online=bot_online,
        uptime_started_at=runtime.get("started_at") if bot_online and runtime else None,
        games=[{"id": game["id"], "name": game["name"]} for game in get_games() if game.get("enabled", True)],
        regions=[{"id": region["id"], "name": region["name"]} for region in get_regions() if region.get("enabled", True)],
        timezones=MAJOR_TIMEZONES,
    )


@api.get("/api/admin")
@_login_required
def owner_admin_data():
    identity = request.website_identity
    if not _is_bot_owner(identity):
        return jsonify(error="Only the configured bot owner can access this panel."), 403
    runtime = read_runtime_snapshot() or {}
    servers = read_servers()
    known_guilds = {str(item.get("id")): item for item in runtime.get("guilds", [])}
    guild_rows = []
    for guild_id, guild in known_guilds.items():
        settings = servers.get(guild_id, {})
        guild_rows.append({
            "id": guild_id,
            "name": guild.get("name", "Unknown server"),
            "member_count": guild.get("member_count", 0),
            "team_count": len(settings.get("teams", [])),
            "team_names": [team.get("team_name", "Unnamed team") for team in settings.get("teams", [])],
            "setup_complete": bool(settings.get("SetupComplete", False)),
            "team_creation_blacklisted": bool(settings.get("team_creation_blacklisted", False)),
            "update_logs_configured": bool(settings.get("update_logs_channel")),
        })
    return jsonify(
        servers=sorted(guild_rows, key=lambda item: item["name"].casefold()),
        banned_server_ids=sorted(get_banned_server_ids()),
        statuses=list_statuses(),
        update_text=_read_update_text(),
        version=read_version(),
        heartbeat_at=runtime.get("heartbeat_at"),
    )


@api.get("/api/guilds/<guild_id>")
@_login_required
def guild_data(guild_id: str):
    identity = request.website_identity
    membership = _guild_permissions(identity).get(guild_id)
    if membership is None:
        return jsonify(error="This server is not available to your account."), 404
    is_admin = _is_admin(membership)
    is_suggestion_owner = bool(membership.get("owner") and guild_id == str(SUGGESTION_GUILD_ID))
    server = read_servers().get(guild_id)
    if server is None:
        if not is_admin:
            return jsonify(error="This server is not available to your account."), 404
        server = {}
    runtime = read_runtime_snapshot() or {}
    catalog = next(
        (item for item in runtime.get("guild_catalog", []) if item.get("id") == guild_id),
        {},
    )
    teams = []
    for team in server.get("teams", []):
        is_captain = str(team.get("team_captain_id", "")) == str(identity["user"]["id"])
        if not is_admin and not is_captain:
            continue
        teams.append({
            "team_name": team.get("team_name", "Unnamed team"),
            "game_id": team.get("game_id", ""),
            "region_id": team.get("region_id", ""),
            "team_captain_id": str(team.get("team_captain_id", "")),
            "team_role_id": str(team.get("team_role_id", "")),
            "team_schedule_channel": str(team.get("team_schedule_channel", "")),
            "team_request_channel": str(team.get("team_request_channel", "")),
            "timezone": team.get("timezone", "UTC"),
            "scrim_requests_enabled": bool(team.get("scrim_requests_enabled", True)),
            "can_manage": is_admin,
            "is_captain": is_captain,
        })
    return jsonify(
        id=guild_id,
        name=membership.get("name", "Discord server"),
        can_manage=is_admin,
        setup_complete=bool(server.get("SetupComplete", False)),
        team_creation_disabled=bool(server.get("team_creation_blacklisted", False)),
        settings={
            "bot_channels": [str(value) for value in server.get("bot_channels", [])],
            "admin_roles": [str(value) for value in server.get("admin_roles", [])],
            "update_logs_channel": str(server.get("update_logs_channel", "")),
            "bot_logs_channel": str(server.get("bot_logs_channel", "")),
        },
        roles=catalog.get("roles", []) if is_admin else [],
        channels=catalog.get("channels", []) if is_admin else [],
        can_moderate_suggestions=is_suggestion_owner,
        blacklisted_suggesters=get_blacklisted_suggesters() if is_suggestion_owner else [],
        teams=teams,
    )


@api.get("/api/actions")
@_login_required
def action_history():
    identity = request.website_identity
    guilds = _authorized_guilds(identity)
    guild_ids = {item["id"] for item in guilds}
    if _is_bot_owner(identity):
        guild_ids.add("0")
    actions = list_user_actions(identity["user"]["id"], guild_ids)
    return jsonify(actions=actions)


@api.post("/api/actions")
@_login_required
def submit_action():
    identity = request.website_identity
    if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), identity.get("csrf_token", "")):
        return jsonify(error="Request could not be verified."), 403
    data = request.get_json(silent=True) or {}
    action_type = data.get("type")
    guild_id = str(data.get("guild_id", ""))
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        return jsonify(error="Action details must be an object."), 400
    is_bot_owner = _is_bot_owner(identity)
    owner_actions = {
        "owner.version_set", "owner.update_broadcast", "owner.status_add", "owner.status_remove", "owner.status_enable",
        "owner.status_refresh", "owner.sync_commands", "owner.refresh_help_docs",
        "owner.server_blacklist", "owner.server_ban",
    }
    if action_type in owner_actions:
        if not is_bot_owner:
            return jsonify(error="Only the configured bot owner can do that."), 403
        if guild_id != "0":
            return jsonify(error="Bot-owner actions must use the global queue scope."), 400
        if action_type == "owner.version_set" and not 1 <= len(str(payload.get("version", "")).strip()) <= 30:
            return jsonify(error="Version must contain 1 to 30 characters."), 400
        if action_type == "owner.update_broadcast" and not 1 <= len(str(payload.get("text", "")).strip()) <= 1800:
            return jsonify(error="Update text must contain 1 to 1800 characters."), 400
        if action_type in {"owner.status_add", "owner.status_remove", "owner.status_enable"} and not 1 <= len(str(payload.get("text", "")).strip()) <= 100:
            return jsonify(error="Status text must contain 1 to 100 characters."), 400
        if action_type in {"owner.server_blacklist", "owner.server_ban"}:
            target_id = str(payload.get("target_guild_id", ""))
            if not target_id.isdigit():
                return jsonify(error="Choose a valid server."), 400
            if action_type == "owner.server_blacklist" and not isinstance(payload.get("blacklisted"), bool):
                return jsonify(error="Team creation state must be enabled or disabled."), 400
            if action_type == "owner.server_ban" and payload.get("confirm_id") != target_id:
                return jsonify(error="Confirm the server ID before banning it."), 400
        action_id = enqueue_action("0", identity["user"]["id"], action_type, payload)
        return jsonify(action_id=action_id, status="pending"), 202

    membership = _guild_permissions(identity).get(guild_id)
    server = read_servers().get(guild_id, {})
    if membership is None:
        return jsonify(error="This server is not available to your account."), 404
    is_admin = _is_admin(membership)
    if not server and not is_admin:
        return jsonify(error="This server is not available to your account."), 404
    team_name = str(payload.get("team_name", ""))
    team = next((item for item in server.get("teams", []) if item.get("team_name", "").casefold() == team_name.casefold()), None)
    is_captain = bool(team and str(team.get("team_captain_id", "")) == str(identity["user"]["id"]))

    if action_type == "server.settings_update":
        fields = payload.get("fields", {})
        allowed_settings = {"bot_channels", "admin_roles", "update_logs_channel", "bot_logs_channel", "SetupComplete"}
        if not is_admin:
            return jsonify(error="Only server administrators can change server settings."), 403
        if not isinstance(fields, dict) or not fields or not set(fields).issubset(allowed_settings):
            return jsonify(error="Choose valid server settings."), 400
        if any(key in fields and not isinstance(fields[key], list) for key in ("bot_channels", "admin_roles")):
            return jsonify(error="Bot channels and admin roles must be selected as lists."), 400
        for key in ("update_logs_channel", "bot_logs_channel"):
            if key in fields and fields[key] not in {"", None} and not str(fields[key]).isdigit():
                return jsonify(error=f"{key.replace('_', ' ').title()} must be selected from this server."), 400
        if "SetupComplete" in fields and fields["SetupComplete"] is not True:
            return jsonify(error="Setup can only be marked complete."), 400
    elif action_type == "team.create":
        if not is_admin:
            return jsonify(error="Only server owners and administrators can create teams."), 403
        required = ("team_name", "game_id", "team_captain_id", "team_role_id", "team_schedule_channel", "team_request_channel", "timezone")
        if any(not str(payload.get(key, "")).strip() for key in required):
            return jsonify(error="Complete every team field before submitting."), 400
        if server.get("team_creation_blacklisted"):
            return jsonify(error="Team creation is disabled for this server."), 403
    elif action_type == "team.update":
        fields = payload.get("fields", {})
        if team is None or not isinstance(fields, dict) or not fields:
            return jsonify(error="Choose an existing team and at least one setting."), 400
        captain_fields = {"region_id", "scrim_requests_enabled"}
        if not team.get("game_id"):
            captain_fields.add("game_id")
        if not is_admin and (not is_captain or not set(fields).issubset(captain_fields)):
            return jsonify(error="You cannot change those team settings."), 403
    elif action_type in {"suggestion.blacklist", "suggestion.unblacklist"}:
        if not membership.get("owner") or guild_id != str(SUGGESTION_GUILD_ID):
            return jsonify(error="Only the owner of the configured suggestion server can manage this list."), 403
        if not str(payload.get("target_user_id", "")).isdigit() or int(payload["target_user_id"]) <= 0:
            return jsonify(error="Enter a valid Discord user ID."), 400
    elif action_type in {"team.delete", "schedule.send", "event.create"}:
        if team is None:
            return jsonify(error="Choose an existing team."), 400
        if not is_admin and not is_captain:
            return jsonify(error="Only the team captain or a server administrator can do that."), 403
        if action_type == "event.create" and any(not str(payload.get(key, "")).strip() for key in ("event_name", "date", "time")):
            return jsonify(error="Enter an activity name, date, and time."), 400
        if action_type == "team.delete" and not is_admin:
            return jsonify(error="Only server administrators can delete teams."), 403
    else:
        return jsonify(error="That action is not supported."), 400

    action_id = enqueue_action(guild_id, identity["user"]["id"], action_type, payload)
    return jsonify(action_id=action_id, status="pending"), 202