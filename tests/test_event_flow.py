import importlib
import sys
import types
import unittest


def _install_fake_discord():
    discord = types.ModuleType("discord")

    class LayoutView:
        def __init__(self, timeout=None):
            self.timeout = timeout
            self.items = []

        def add_item(self, item):
            self.items.append(item)

    class ActionRow:
        pass

    class Button:
        pass

    class TextDisplay:
        def __init__(self, content):
            self.content = content

    class Container:
        def __init__(self, accent_color=None):
            self.accent_color = accent_color
            self.items = []

        def add_item(self, item):
            self.items.append(item)

    class Separator:
        def __init__(self, spacing=None):
            self.spacing = spacing

    class SeparatorSpacing:
        small = "small"
        large = "large"

    class ButtonStyle:
        success = "success"
        secondary = "secondary"
        danger = "danger"

    class Color:
        @staticmethod
        def purple():
            return "purple"

    class Interaction:
        pass

    def button(**_kwargs):
        def decorator(func):
            return func

        return decorator

    discord.ButtonStyle = ButtonStyle
    discord.Color = Color
    discord.Interaction = Interaction
    discord.SeparatorSpacing = SeparatorSpacing
    discord.ui = types.SimpleNamespace(
        LayoutView=LayoutView,
        ActionRow=ActionRow,
        Button=Button,
        TextDisplay=TextDisplay,
        Container=Container,
        Separator=Separator,
        SeparatorSpacing=SeparatorSpacing,
        button=button,
    )
    sys.modules["discord"] = discord


_install_fake_discord()
fake_command_helpers = types.ModuleType("utils.command_helpers")


class _CommandResponse:
    @staticmethod
    async def error(*_args, **_kwargs):
        return None

    @staticmethod
    async def followup_success(*_args, **_kwargs):
        return None

    @staticmethod
    async def followup_info(*_args, **_kwargs):
        return None


fake_command_helpers.CommandResponse = _CommandResponse
sys.modules["utils.command_helpers"] = fake_command_helpers

fake_funcs = types.ModuleType("utils.funcs")


async def _log_to_discord(*_args, **_kwargs):
    return None


fake_funcs.log_to_discord = _log_to_discord
sys.modules["utils.funcs"] = fake_funcs

event_flow = importlib.import_module("utils.event_flow")


class EventFlowFormattingTests(unittest.TestCase):
    def test_mention_list_uses_real_line_breaks(self):
        self.assertEqual(event_flow._mention_list([1, 2]), "<@1>\n<@2>")
        self.assertEqual(event_flow._mention_list([]), "No one yet")

    def test_activity_card_meta_uses_real_line_breaks(self):
        view = event_flow.EventRSVPLayoutView(
            event_cog=object(),
            guild_id="1",
            message_id=42,
            event_data={"event_name": "Practice event"},
            team_role_mention="@Test role",
            unix_time=1790451600,
            tz_name="London",
        )

        self.assertNotIn("\\n", view.meta.content)
        self.assertEqual(
            view.meta.content,
            "@Test role\n"
            "**Event Time:** <t:1790451600:F> (London)\n"
            "**Relative:** <t:1790451600:R>\n"
            "Use the buttons below to RSVP.",
        )

    def test_activity_card_attendance_uses_real_line_breaks(self):
        view = event_flow.EventRSVPLayoutView(
            event_cog=object(),
            guild_id="1",
            message_id=42,
            event_data={"event_name": "Practice event", "attend": [1], "maybe": [], "cant": [2]},
            team_role_mention="@Test role",
            unix_time=1790451600,
            tz_name="London",
        )

        self.assertNotIn("\\n", view.attendance.content)
        self.assertEqual(
            view.attendance.content,
            "### Can Attend ✅ (1)\n<@1>\n\n"
            "### May be able to 🤔 (0)\nNo one yet\n\n"
            "### Can't Attend ❌ (1)\n<@2>",
        )


if __name__ == "__main__":
    unittest.main()
