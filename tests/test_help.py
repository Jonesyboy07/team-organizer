import os
import unittest
from unittest.mock import patch

from cogs.help import _website_base_url


class HelpCommandTests(unittest.TestCase):
    def test_website_base_url_uses_env_value_without_trailing_slash(self):
        with patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dashboard.example.com/"}, clear=False):
            self.assertEqual(_website_base_url(), "https://dashboard.example.com")

    def test_website_base_url_is_blank_when_unset(self):
        with patch.dict(os.environ, {"WEBSITE_BASE_URL": ""}, clear=False):
            self.assertEqual(_website_base_url(), "")


if __name__ == "__main__":
    unittest.main()
