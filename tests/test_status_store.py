import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils.status_store import disable_status, enable_status


class StatusEnableTests(unittest.TestCase):
    def test_enable_restores_disabled_default_and_custom_statuses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            defaults = Path(tmpdir) / "default.json"
            custom = Path(tmpdir) / "custom.json"
            defaults.write_text(json.dumps([{"text": "Default {servers}", "enabled": False}]), encoding="utf-8")
            custom.write_text(json.dumps([{"text": "Custom", "enabled": False}]), encoding="utf-8")

            with patch("utils.status_store.DEFAULT_STATUSES_FILE", str(defaults)), patch(
                "utils.status_store.CUSTOM_STATUSES_FILE", str(custom)
            ):
                self.assertEqual(disable_status("Custom")["source"], "custom")
                enabled_custom = enable_status("CUSTOM")
                enabled_default = enable_status("Default {servers}")

            self.assertTrue(enabled_custom["enabled"])
            self.assertEqual(enabled_custom["source"], "custom")
            self.assertTrue(enabled_default["enabled"])
            self.assertEqual(enabled_default["source"], "default")


if __name__ == "__main__":
    unittest.main()