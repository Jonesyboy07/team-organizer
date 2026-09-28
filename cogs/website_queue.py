import asyncio
from datetime import datetime, timezone

import discord
import pytz
from discord.ext import commands, tasks

from utils.constants import MAJOR_TIMEZONES
from utils.event_flow import EventRSVPLayoutView
from utils.funcs import CheckIfAdminRole, log_to_discord
from utils.game_service import SUGGESTION_GUILD_ID, blacklist_suggester, get_game, unblacklist_suggester
from utils.owner_config import get_owner_id
from utils.schedule_flow import get_previous_monday, send_weekly_schedule_messages
from utils.server_store import (
    ban_server,
    get_server,
    is_setup_complete,
    read_servers,
    save_teams,
    set_server,
    set_team_creation_blacklist,
)
from utils.status_store import add_custom_status, disable_status, enable_status
from utils.team_service import find_team_by_name, resolve_team_timezone
from utils.website_queue import claim_next_action, finish_action, initialize_queue, write_runtime_snapshot
from utils.version_store import write_version
from utils.website_owner_actions import require_bot_owner


class WebsiteQueueCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        if not self.process_actions.is_running():
            self.process_actions.start()
        if not self.publish_runtime.is_running():
            self.publish_runtime.start()

    async def cog_unload(self):
        self.process_actions.cancel()
        self.publish_runtime.cancel()

    @tasks.loop(seconds=30)
    async def publish_runtime(self):
        started_at = getattr(self.bot, "started_at", datetime.now(timezone.utc)).isoformat()
        guild_catalog = [{
            "id": str(guild.id),
            "roles": [
                {"id": str(role.id), "name": role.name}
                for role in guild.roles
                if not role.is_default()
            ],
            "channels": [
                {"id": str(channel.id), "name": f"#{channel.name}"}
                for channel in guild.text_channels
            ],
        } for guild in self.bot.guilds]
        guilds = [{
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count or 0,
        } for guild in self.bot.guilds]
        await asyncio.to_thread(
            write_runtime_snapshot,
            started_at,
            len(self.bot.guilds),
            guild_catalog,
            guilds,
        )

    @publish_runtime.before_loop
    async def wait_for_runtime_ready(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=2)
    async def process_actions(self):
        try:
            action = await asyncio.to_thread(claim_next_action)
            if action is None:
                return
            try:
                result = await self._execute(action)
            except Exception as exc:  # noqa: BLE001
                finish_action(action["action_id"], "failed", str(exc) or "The bot could not complete this action.")
                await self._log(action, f"Website action failed: {exc}")
            else:
                finish_action(action["action_id"], "completed", result)
                await self._log(action, f"Website action completed: {action['action_type']} by user {action['user_id']}")
        except Exception as exc:  # noqa: BLE001
            print(f"[WebsiteQueueCog] Queue polling failed: {exc}")

    @process_actions.before_loop
    async def wait_until_ready(self):
        await self.bot.wait_until_ready()
        initialize_queue()

    async def _log(self, action: dict, message: str):
        try:
            await log_to_discord(self.bot, action["guild_id"], message)
        except Exception as exc:  # noqa: BLE001
            print(f"[WebsiteQueueCog] Could not log action: {exc}")

    async def _execute(self, action: dict) -> str:
        if action["action_type"].startswith("owner."):
            require_bot_owner(action["user_id"], get_owner_id())
            return await self._execute_owner_action(action)

        guild_id = int(action["guild_id"])
        user_id = int(action["user_id"])
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            raise ValueError("The bot is no longer a member of this server.")
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound as exc:
                raise ValueError("The requesting user is no longer a member of this server.") from exc

        server = get_server(guild_id)
        teams = server.get("teams", [])
        team_name = action["payload"].get("team_name", "")
        team = find_team_by_name(teams, team_name) if team_name else None
        is_owner = member.id == guild.owner_id
        is_admin = (
            is_owner
            or member.guild_permissions.administrator
            or CheckIfAdminRole([role.id for role in member.roles], str(guild_id))
        )
        is_captain = bool(team and member.id == int(team.get("team_captain_id", 0)))
        action_type = action["action_type"]
        payload = action["payload"]

        if action_type == "team.create":
            if not is_admin:
                raise PermissionError("Only server owners and configured server admins can create teams.")
            self._create_team(guild, server, payload)
            return f"Team {payload['team_name']} created."
        if action_type == "team.update":
            if team is None:
                raise ValueError("That team no longer exists.")
            fields = payload.get("fields", {})
            captain_fields = {"region_id", "scrim_requests_enabled"}
            if not team.get("game_id"):
                captain_fields.add("game_id")
            owner_fields = {
                "team_name", "team_captain_id", "team_role_id", "team_schedule_channel",
                "team_request_channel", "timezone", "region_id", "scrim_requests_enabled", "game_id",
            }
            if not is_admin and (not is_captain or not set(fields).issubset(captain_fields)):
                raise PermissionError("You no longer have permission to edit these team settings.")
            if not fields or not set(fields).issubset(owner_fields):
                raise ValueError("The requested team settings are not supported.")
            self._update_team(guild, teams, team, fields)
            return f"Settings saved for {team['team_name']}."
        if action_type == "team.delete":
            if not is_admin:
                raise PermissionError("Only server owners and configured server admins can delete teams.")
            if team is None:
                raise ValueError("That team no longer exists.")
            teams.remove(team)
            save_teams(guild_id, teams)
            return f"Team {team_name} deleted."
        if action_type == "server.settings_update":
            if not is_admin:
                raise PermissionError("Only server administrators can change server settings.")
            fields = payload.get("fields", {})
            if not fields or not set(fields).issubset({"bot_channels", "admin_roles", "update_logs_channel", "bot_logs_channel", "SetupComplete"}):
                raise ValueError("Unsupported server settings were requested.")
            if "SetupComplete" in fields:
                if fields["SetupComplete"] is not True:
                    raise ValueError("Setup can only be marked complete after configuration.")
                configured_bot_channels = fields.get("bot_channels", server.get("bot_channels", []))
                configured_admin_roles = fields.get("admin_roles", server.get("admin_roles", []))
                configured_update_channel = fields.get("update_logs_channel", server.get("update_logs_channel", ""))
                configured_bot_log_channel = fields.get("bot_logs_channel", server.get("bot_logs_channel", ""))
                if not configured_bot_channels or not configured_admin_roles:
                    raise ValueError("Configure at least one command channel and administrator role first.")
                if not configured_update_channel or not configured_bot_log_channel:
                    raise ValueError("Configure both update and bot log channels first.")
                fields["SetupComplete"] = True
            for key in ("bot_channels", "admin_roles"):
                if key in fields:
                    if not isinstance(fields[key], list):
                        raise ValueError(f"{key} must be a list of Discord IDs.")
                    values = []
                    for raw_id in fields[key]:
                        try:
                            identifier = int(raw_id)
                        except (TypeError, ValueError) as exc:
                            raise ValueError(f"Invalid ID in {key}.") from exc
                        if key == "bot_channels":
                            if not isinstance(guild.get_channel(identifier), discord.TextChannel):
                                raise ValueError("Every bot command channel must be a text channel in this server.")
                        elif guild.get_role(identifier) is None:
                            raise ValueError("Every configured admin role must belong to this server.")
                        values.append(str(identifier))
                    fields[key] = values
            for key in ("update_logs_channel", "bot_logs_channel"):
                if key in fields:
                    if fields[key] in {"", None}:
                        server[key] = ""
                        continue
                    try:
                        channel_id = int(fields[key])
                    except (TypeError, ValueError) as exc:
                        raise ValueError(f"{key} must be a text channel ID.") from exc
                    if not isinstance(guild.get_channel(channel_id), discord.TextChannel):
                        raise ValueError(f"{key} must be a text channel in this server.")
                    fields[key] = str(channel_id)
            server.update(fields)
            server.setdefault("teams", [])
            server.setdefault("leagues", [])
            set_server(guild_id, server)
            return "Server settings saved."
        if action_type in {"suggestion.blacklist", "suggestion.unblacklist"}:
            if not is_admin:
                raise PermissionError("Only server admins can manage suggestion access.")
            if guild_id != str(SUGGESTION_GUILD_ID):
                raise PermissionError("Suggestion moderation is only available in the configured suggestion server.")
            try:
                target_user_id = int(payload.get("target_user_id", 0))
            except (TypeError, ValueError) as exc:
                raise ValueError("Enter a valid Discord user ID.") from exc
            if target_user_id <= 0:
                raise ValueError("Enter a valid Discord user ID.")
            if action_type == "suggestion.blacklist":
                blacklist_suggester(target_user_id)
                return f"User {target_user_id} is blocked from suggesting games."
            if not unblacklist_suggester(target_user_id):
                raise ValueError("That user is not currently blacklisted.")
            return f"User {target_user_id} can suggest games again."
        if action_type == "schedule.send":
            if not is_admin and not is_captain:
                raise PermissionError("Only a team captain or server admin can send scheduling.")
            channel_id = team.get("team_schedule_channel") if team else None
            channel = guild.get_channel(int(channel_id)) if channel_id else None
            if team is None or not isinstance(channel, discord.TextChannel):
                raise ValueError("The team's schedule channel is not configured or available.")
            now = datetime.now(resolve_team_timezone(team))
            role_id = team.get("team_role_id")
            await send_weekly_schedule_messages(
                channel,
                f"<@&{role_id}>" if role_id else "",
                get_previous_monday(now),
                team,
            )
            current = get_server(guild_id)
            current_teams = current.get("teams", [])
            current_team = find_team_by_name(current_teams, team_name)
            if current_team:
                current_team["last_synced"] = now.strftime("%Y-%m-%d")
                save_teams(guild_id, current_teams)
            return f"Weekly scheduling messages sent for {team_name}."
        if action_type == "event.create":
            if not is_admin and not is_captain:
                raise PermissionError("Only a team captain or server admin can create an activity.")
            return await self._create_event(guild, team, payload)
        raise ValueError("Unknown website action.")

    async def _execute_owner_action(self, action: dict) -> str:
        action_type = action["action_type"]
        payload = action["payload"]
        if action_type == "owner.version_set":
            return f"Bot version set to {write_version(payload.get('version', ''))}."
        if action_type == "owner.status_add":
            created, entry = add_custom_status(payload.get("text", ""))
            return f"{'Added' if created else 'Re-enabled'} status: {entry['text']}"
        if action_type == "owner.status_remove":
            entry = disable_status(payload.get("text", ""))
            if entry is None:
                raise ValueError("No matching status was found.")
            return f"Disabled status: {entry['text']}"
        if action_type == "owner.status_enable":
            entry = enable_status(payload.get("text", ""))
            if entry is None:
                raise ValueError("No matching status was found.")
            return f"Enabled status: {entry['text']}"
        if action_type == "owner.status_refresh":
            cog = self.bot.get_cog("StatusCog")
            if cog is None:
                raise RuntimeError("Status controls are unavailable.")
            return f"Bot status refreshed: {await cog._apply_next_status()}"
        if action_type == "owner.sync_commands":
            commands_synced = await self.bot.tree.sync()
            return f"Synced {len(commands_synced)} application commands."
        if action_type == "owner.refresh_help_docs":
            from utils.command_docs import sync_commands_json

            count = sync_commands_json(self.bot)
            return f"Refreshed help documentation for {count} commands."
        if action_type == "owner.update_broadcast":
            text = payload.get("text", "").strip()
            if not text or len(text) > 1800:
                raise ValueError("Update text must contain 1 to 1800 characters.")
            with open("data/update.txt", "w", encoding="utf-8") as handle:
                handle.write(text)
            servers = read_servers()
            sent = 0
            failed = 0
            for target_guild_id, data in servers.items():
                channel_id = data.get("update_logs_channel")
                target_guild = self.bot.get_guild(int(target_guild_id))
                channel = target_guild.get_channel(int(channel_id)) if target_guild and channel_id else None
                if not isinstance(channel, discord.TextChannel):
                    failed += 1
                    continue
                try:
                    await channel.send(f"📢 **Update:**\n{text}")
                    sent += 1
                except discord.HTTPException:
                    failed += 1
            return f"Broadcast sent to {sent} server(s); {failed} failed or unconfigured."
        if action_type in {"owner.server_blacklist", "owner.server_ban"}:
            target_id = str(payload.get("target_guild_id", ""))
            if not target_id.isdigit():
                raise ValueError("Choose a valid server.")
            if action_type == "owner.server_blacklist":
                blacklisted = payload.get("blacklisted")
                if not isinstance(blacklisted, bool):
                    raise ValueError("Team creation state must be enabled or disabled.")
                set_team_creation_blacklist(target_id, blacklisted)
                state = "disabled" if blacklisted else "enabled"
                return f"Team creation {state} for server {target_id}."
            if payload.get("confirm_id") != target_id:
                raise ValueError("The server ID confirmation did not match.")
            ban_server(target_id)
            target_guild = self.bot.get_guild(int(target_id))
            if target_guild:
                await target_guild.leave()
            return f"Server {target_id} banned; bot left if it was still a member."
        raise ValueError("Unknown owner action.")

    @staticmethod
    def _create_team(guild, server: dict, payload: dict):
        if not is_setup_complete(guild.id):
            raise ValueError("Complete bot setup in this server before creating teams.")
        if server.get("team_creation_blacklisted"):
            raise PermissionError("Team creation is disabled for this server.")
        name = payload.get("team_name", "").strip()
        if not 2 <= len(name) <= 50:
            raise ValueError("Team names must be between 2 and 50 characters.")
        teams = server.get("teams", [])
        if any(item.get("team_name", "").casefold() == name.casefold() for item in teams):
            raise ValueError("A team with that name already exists.")
        game = get_game(payload.get("game_id", ""))
        timezone_label = payload.get("timezone", "")
        if game is None or timezone_label not in MAJOR_TIMEZONES:
            raise ValueError("Choose a supported game and timezone.")
        captain = guild.get_member(int(payload.get("team_captain_id", 0)))
        role = guild.get_role(int(payload.get("team_role_id", 0)))
        schedule = guild.get_channel(int(payload.get("team_schedule_channel", 0)))
        request = guild.get_channel(int(payload.get("team_request_channel", 0)))
        if captain is None or role is None or not isinstance(schedule, discord.TextChannel) or not isinstance(request, discord.TextChannel):
            raise ValueError("Captain, role, and both text channels must belong to this server.")
        teams.append({
            "team_name": name,
            "game_id": game["id"],
            "team_captain_id": captain.id,
            "team_role_id": role.id,
            "team_schedule_channel": schedule.id,
            "team_request_channel": request.id,
            "timezone": timezone_label,
            "scrim_requests_enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        server["teams"] = teams
        set_server(guild.id, server)

    @staticmethod
    def _update_team(guild, teams: list, team: dict, fields: dict):
        normalized = dict(fields)
        for key in ("team_captain_id", "team_role_id", "team_schedule_channel", "team_request_channel"):
            if key in normalized:
                try:
                    normalized[key] = int(normalized[key])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key.replace('_', ' ').title()} must be a numeric ID.") from exc
        if "team_name" in normalized:
            name = str(normalized["team_name"]).strip()
            if not 2 <= len(name) <= 50 or any(
                item is not team and item.get("team_name", "").casefold() == name.casefold() for item in teams
            ):
                raise ValueError("Team name is invalid or already in use.")
            normalized["team_name"] = name
        if "timezone" in normalized and normalized["timezone"] not in MAJOR_TIMEZONES:
            raise ValueError("Choose a supported timezone.")
        if "game_id" in normalized:
            selected_game = get_game(normalized["game_id"])
            if selected_game is None:
                raise ValueError("Choose a supported game.")
            normalized["game_id"] = selected_game["id"]
        if "scrim_requests_enabled" in normalized and not isinstance(normalized["scrim_requests_enabled"], bool):
            raise ValueError("Scrim request setting must be enabled or disabled.")
        if "region_id" in normalized and not isinstance(normalized["region_id"], str):
            raise ValueError("Region ID must be text.")
        for key in ("team_captain_id", "team_role_id", "team_schedule_channel", "team_request_channel"):
            if key in normalized:
                identifier = normalized[key]
                if key == "team_captain_id" and guild.get_member(identifier) is None:
                    raise ValueError("The selected captain is not a member of this server.")
                if key == "team_role_id" and guild.get_role(identifier) is None:
                    raise ValueError("The selected team role is not in this server.")
                if key.endswith("channel") and not isinstance(guild.get_channel(identifier), discord.TextChannel):
                    raise ValueError("The selected channel must be a text channel in this server.")
        team.update(normalized)
        save_teams(guild.id, teams)

    async def _create_event(self, guild, team: dict | None, payload: dict) -> str:
        if team is None:
            raise ValueError("That team no longer exists.")
        event_name = payload.get("event_name", "").strip()
        if not 2 <= len(event_name) <= 100:
            raise ValueError("Activity names must be between 2 and 100 characters.")
        try:
            event_date = datetime.strptime(payload.get("date", ""), "%Y-%m-%d")
            event_time = datetime.strptime(payload.get("time", ""), "%H:%M")
            event_dt = resolve_team_timezone(team).localize(
                event_date.replace(hour=event_time.hour, minute=event_time.minute)
            )
        except (ValueError, pytz.exceptions.PytzError) as exc:
            raise ValueError("Use a valid date (YYYY-MM-DD) and time (HH:MM, 24-hour).") from exc
        channel_id = team.get("team_schedule_channel")
        channel = guild.get_channel(int(channel_id)) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("The team's schedule channel is not configured or available.")
        event_cog = self.bot.get_cog("EventCog")
        if event_cog is None:
            raise RuntimeError("The activity service is not available. Try again when the bot is ready.")
        event_data = {
            "event_name": event_name,
            "team_name": team["team_name"],
            "datetime": event_dt.isoformat(),
            "attend": [],
            "maybe": [],
            "cant": [],
        }
        unix_time = int(event_dt.timestamp())
        message = await channel.send("Creating activity card...")
        view = EventRSVPLayoutView(
            event_cog=event_cog,
            guild_id=str(guild.id),
            message_id=message.id,
            event_data=event_data,
            team_role_mention=f"<@&{team['team_role_id']}>" if team.get("team_role_id") else "",
            unix_time=unix_time,
            tz_name=team.get("timezone", "UTC"),
        )
        await message.edit(content=None, view=view)
        events = event_cog.load_events(str(guild.id))
        events[str(message.id)] = event_data
        event_cog.save_events(str(guild.id), events)
        return f"Activity {event_name} created in #{channel.name}."


async def setup(bot: commands.Bot):
    await bot.add_cog(WebsiteQueueCog(bot))