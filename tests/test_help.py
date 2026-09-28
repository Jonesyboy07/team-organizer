import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cogs.help import HelpCog, _website_base_url


class HelpCommandTests(unittest.TestCase):
    def test_website_base_url_uses_env_value_without_trailing_slash(self):
        with patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dashboard.example.com/"}, clear=False):
            self.assertEqual(_website_base_url(), "https://dashboard.example.com")

    def test_website_base_url_is_blank_when_unset(self):
        with patch.dict(os.environ, {"WEBSITE_BASE_URL": ""}, clear=False):
            self.assertEqual(_website_base_url(), "")


class WebsiteSlashCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_website_command_in_dm_does_not_check_bot_channel(self):
        cog = HelpCog(SimpleNamespace())
        interaction = SimpleNamespace(
            guild_id=None,
            channel_id=123,
            response=SimpleNamespace(send_message=AsyncMock()),
        )
        with patch.dict(os.environ, {"WEBSITE_BASE_URL": "https://dashboard.example.com"}, clear=False), patch(
            "cogs.help.CheckIfBotChannel"
        ) as check:
            await HelpCog.website_command.callback(cog, interaction)

        check.assert_not_called()
        interaction.response.send_message.assert_awaited_once_with(
            "🌐 Team Organizer website: https://dashboard.example.com",
            ephemeral=True,
        )


if __name__ == "__main__":
    unittest.main()
