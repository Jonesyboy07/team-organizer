import unittest
import os
from unittest.mock import patch

from website import create_app


class WebsiteApiAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()
        self.identity = {
            "user": {"id": "42", "username": "captain"},
            "csrf_token": "csrf-test",
            "guilds": [{"id": "100", "name": "Scrim server", "owner": False, "permissions": "0"}],
        }
        self.servers = {
            "100": {
                "SetupComplete": True,
                "teams": [{"team_name": "Alpha", "team_captain_id": 42}],
            }
        }

    def post_action(self, action_type, payload, identity=None):
        with patch("website.api._identity", return_value=identity or self.identity), patch(
            "website.api.read_servers", return_value=self.servers
        ), patch("website.api.enqueue_action", return_value="action-1") as enqueue:
            response = self.client.post(
                "/api/actions",
                json={"type": action_type, "guild_id": "100", "payload": payload},
                headers={"X-CSRF-Token": "csrf-test"},
            )
        return response, enqueue

    def test_team_captain_can_queue_schedule_action(self):
        response, enqueue = self.post_action("schedule.send", {"team_name": "Alpha"})

        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once_with("100", "42", "schedule.send", {"team_name": "Alpha"})

    def test_non_captain_cannot_queue_team_action(self):
        outsider = {**self.identity, "user": {"id": "43", "username": "member"}}

        response, enqueue = self.post_action("schedule.send", {"team_name": "Alpha"}, outsider)

        self.assertEqual(response.status_code, 403)
        enqueue.assert_not_called()

    def test_captain_can_assign_only_an_unset_game(self):
        response, enqueue = self.post_action(
            "team.update",
            {"team_name": "Alpha", "fields": {"game_id": "game-1"}},
        )
        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once()

        self.servers["100"]["teams"][0]["game_id"] = "existing-game"
        response, enqueue = self.post_action(
            "team.update",
            {"team_name": "Alpha", "fields": {"game_id": "game-2"}},
        )
        self.assertEqual(response.status_code, 403)
        enqueue.assert_not_called()

    def test_only_server_owner_or_admin_can_create_team(self):
        payload = {
            "team_name": "Bravo",
            "game_id": "game-id",
            "team_captain_id": "43",
            "team_role_id": "44",
            "team_schedule_channel": "45",
            "team_request_channel": "46",
            "timezone": "UTC",
        }
        response, enqueue = self.post_action("team.create", payload)
        self.assertEqual(response.status_code, 403)
        enqueue.assert_not_called()

        owner = {**self.identity, "guilds": [{**self.identity["guilds"][0], "owner": True}]}
        response, enqueue = self.post_action("team.create", payload, owner)
        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once()

    def test_owner_admin_endpoint_is_hidden_from_non_owner(self):
        with patch("website.api._identity", return_value=self.identity):
            denied = self.client.get("/api/admin")
        self.assertEqual(denied.status_code, 403)

        owner = {**self.identity, "user": {"id": "950", "username": "owner"}}
        with patch.dict(os.environ, {"OWNER_ID": "950"}), patch("website.api._identity", return_value=owner), patch(
            "website.api.read_runtime_snapshot", return_value={"guilds": [], "heartbeat_at": "now"}
        ), patch("website.api.read_servers", return_value={}), patch(
            "website.api.get_banned_server_ids", return_value=set()
        ), patch("website.api.list_statuses", return_value=[]), patch(
            "website.api._read_update_text", return_value="Update"
        ):
            response = self.client.get("/api/admin")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["statuses"], [])

    def test_owner_global_action_uses_global_queue_scope(self):
        owner = {**self.identity, "user": {"id": "950", "username": "owner"}}
        with patch.dict(os.environ, {"OWNER_ID": "950"}), patch(
            "website.api._identity", return_value=owner
        ), patch("website.api.enqueue_action", return_value="global-action") as enqueue:
            response = self.client.post(
                "/api/actions",
                json={"type": "owner.version_set", "guild_id": "0", "payload": {"version": "4.0"}},
                headers={"X-CSRF-Token": "csrf-test"},
            )

        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once_with("0", "950", "owner.version_set", {"version": "4.0"})

    def test_owner_server_ban_requires_matching_confirmation(self):
        owner = {**self.identity, "user": {"id": "950", "username": "owner"}}
        with patch.dict(os.environ, {"OWNER_ID": "950"}), patch(
            "website.api._identity", return_value=owner
        ), patch("website.api.enqueue_action", return_value="global-action") as enqueue:
            response = self.client.post(
                "/api/actions",
                json={"type": "owner.server_ban", "guild_id": "0", "payload": {"target_guild_id": "100"}},
                headers={"X-CSRF-Token": "csrf-test"},
            )

        self.assertEqual(response.status_code, 400)
        enqueue.assert_not_called()

    def test_owner_can_queue_status_enable_action(self):
        owner = {**self.identity, "user": {"id": "950", "username": "owner"}}
        with patch.dict(os.environ, {"OWNER_ID": "950"}), patch(
            "website.api._identity", return_value=owner
        ), patch("website.api.enqueue_action", return_value="status-action") as enqueue:
            response = self.client.post(
                "/api/actions",
                json={"type": "owner.status_enable", "guild_id": "0", "payload": {"text": "Default status"}},
                headers={"X-CSRF-Token": "csrf-test"},
            )
        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once_with("0", "950", "owner.status_enable", {"text": "Default status"})

    def test_server_settings_are_admin_only_and_payload_is_validated(self):
        payload = {"fields": {"admin_roles": ["44"], "bot_channels": ["45"]}}
        response, enqueue = self.post_action("server.settings_update", payload)
        self.assertEqual(response.status_code, 403)
        enqueue.assert_not_called()

        admin = {**self.identity, "guilds": [{**self.identity["guilds"][0], "permissions": str(1 << 3)}]}
        response, enqueue = self.post_action("server.settings_update", payload, admin)
        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once_with("100", "42", "server.settings_update", payload)

    def test_server_admin_can_queue_initial_setup_for_new_guild(self):
        admin = {**self.identity, "guilds": [{**self.identity["guilds"][0], "permissions": str(1 << 3)}]}
        payload = {"fields": {
            "bot_channels": ["45"],
            "admin_roles": ["44"],
            "update_logs_channel": "46",
            "bot_logs_channel": "47",
            "SetupComplete": True,
        }}
        with patch("website.api._identity", return_value=admin), patch(
            "website.api.read_servers", return_value={}
        ), patch("website.api.enqueue_action", return_value="setup-action") as enqueue:
            response = self.client.post(
                "/api/actions",
                json={"type": "server.settings_update", "guild_id": "100", "payload": payload},
                headers={"X-CSRF-Token": "csrf-test"},
            )

        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once_with("100", "42", "server.settings_update", payload)

    def test_suggestion_server_owner_can_manage_blacklist(self):
        suggestion_owner = {**self.identity, "guilds": [{**self.identity["guilds"][0], "owner": True}]}
        payload = {"target_user_id": "123456"}
        with patch("website.api.SUGGESTION_GUILD_ID", 100), patch(
            "website.api._identity", return_value=suggestion_owner
        ), patch("website.api.read_servers", return_value=self.servers), patch(
            "website.api.enqueue_action", return_value="suggestion-action"
        ) as enqueue:
            response = self.client.post(
                "/api/actions",
                json={"type": "suggestion.blacklist", "guild_id": "100", "payload": payload},
                headers={"X-CSRF-Token": "csrf-test"},
            )

        self.assertEqual(response.status_code, 202)
        enqueue.assert_called_once_with("100", "42", "suggestion.blacklist", payload)


if __name__ == "__main__":
    unittest.main()