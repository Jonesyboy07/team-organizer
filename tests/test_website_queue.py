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


if __name__ == "__main__":
    unittest.main()