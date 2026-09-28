import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cogs.games import can_manage_game_suggestions


def _member(*, user_id: int, administrator: bool = False, role_ids: tuple[int, ...] = ()):
    return SimpleNamespace(
        id=user_id,
        guild_permissions=SimpleNamespace(administrator=administrator),
        roles=[SimpleNamespace(id=role_id) for role_id in role_ids],
    )


class GameSuggestionPermissionTests(unittest.TestCase):
    def test_guild_owner_can_manage_game_suggestions(self):
        with patch("cogs.games.CheckIfAdminRole", return_value=False) as check:
            allowed = can_manage_game_suggestions(_member(user_id=42), 42, 100)

        self.assertTrue(allowed)
        check.assert_not_called()

    def test_administrator_can_manage_game_suggestions(self):
        with patch("cogs.games.CheckIfAdminRole", return_value=False) as check:
            allowed = can_manage_game_suggestions(_member(user_id=7, administrator=True), 42, 100)

        self.assertTrue(allowed)
        check.assert_not_called()

    def test_configured_admin_role_can_manage_game_suggestions(self):
        with patch("cogs.games.CheckIfAdminRole", return_value=True) as check:
            allowed = can_manage_game_suggestions(_member(user_id=7, role_ids=(5, 6)), 42, 100)

        self.assertTrue(allowed)
        check.assert_called_once_with([5, 6], "100")

    def test_regular_member_cannot_manage_game_suggestions(self):
        with patch("cogs.games.CheckIfAdminRole", return_value=False) as check:
            allowed = can_manage_game_suggestions(_member(user_id=7, role_ids=(5, 6)), 42, 100)

        self.assertFalse(allowed)
        check.assert_called_once_with([5, 6], "100")


if __name__ == "__main__":
    unittest.main()
