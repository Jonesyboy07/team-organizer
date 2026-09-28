import unittest
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


if __name__ == "__main__":
    unittest.main()