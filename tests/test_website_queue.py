import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cogs.website_queue import WebsiteQueueCog
from utils.website_queue import claim_next_action, enqueue_action, finish_action, list_user_actions
from utils.website_owner_actions import require_bot_owner


class WebsiteQueueTests(unittest.TestCase):
    def test_action_lifecycle_is_persisted_and_scoped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            database = str(Path(tmpdir) / "storage.db")
            with patch("utils.server_store.DB_FILE", database), patch("utils.website_queue.DB_FILE", database):
                action_id = enqueue_action("42", "7", "send_schedule", {"team_name": "Alpha"})
                action = claim_next_action()

                self.assertEqual(action["action_id"], action_id)
                self.assertEqual(action["payload"], {"team_name": "Alpha"})
                finish_action(action_id, "completed", "Schedule sent")

                visible = list_user_actions("7", {"42"})
                hidden = list_user_actions("8", {"42"})
                self.assertEqual(visible[0]["status"], "completed")
                self.assertEqual(visible[0]["result"], "Schedule sent")
                self.assertEqual(hidden, [])

    def test_bot_rejects_forged_owner_action(self):
        with self.assertRaisesRegex(PermissionError, "configured bot owner"):
            require_bot_owner("42", 950)

    def test_configured_owner_can_pass_bot_guard(self):
        self.assertIsNone(require_bot_owner("950", 950))

    def test_queue_loop_intervals_match_dashboard_expectations(self):
        cog = WebsiteQueueCog(SimpleNamespace())

        self.assertEqual(cog.process_actions.seconds, 2.0)
        self.assertEqual(cog.publish_runtime.seconds, 30.0)

    def test_queue_revalidates_team_delete_as_owner_only(self):
        guild = SimpleNamespace(
            owner_id=999,
            get_member=lambda _user_id: SimpleNamespace(
                id=42,
                guild_permissions=SimpleNamespace(administrator=True),
                roles=[],
            ),
        )
        bot = SimpleNamespace(get_guild=lambda _guild_id: guild)
        cog = WebsiteQueueCog(bot)
        action = {
            "guild_id": "100",
            "user_id": "42",
            "action_type": "team.delete",
            "payload": {"team_name": "Alpha"},
        }
        with patch("cogs.website_queue.get_server", return_value={"teams": [{"team_name": "Alpha", "team_captain_id": 42}]}), patch(
            "cogs.website_queue.CheckIfAdminRole", return_value=True
        ):
            with self.assertRaisesRegex(PermissionError, "server owner"):
                asyncio.run(cog._execute(action))

    def test_queue_allows_owner_team_delete(self):
        guild = SimpleNamespace(
            owner_id=42,
            get_member=lambda _user_id: SimpleNamespace(
                id=42,
                guild_permissions=SimpleNamespace(administrator=False),
                roles=[],
            ),
        )
        bot = SimpleNamespace(get_guild=lambda _guild_id: guild)
        cog = WebsiteQueueCog(bot)
        action = {
            "guild_id": "100",
            "user_id": "42",
            "action_type": "team.delete",
            "payload": {"team_name": "Alpha"},
        }
        with patch("cogs.website_queue.get_server", return_value={"teams": [{"team_name": "Alpha", "team_captain_id": 42}]}), patch(
            "cogs.website_queue.save_teams"
        ) as save:
            result = asyncio.run(cog._execute(action))

        self.assertEqual(result, "Team Alpha deleted.")
        save.assert_called_once_with(100, [])


if __name__ == "__main__":
    unittest.main()