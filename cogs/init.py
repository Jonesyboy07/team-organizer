from cogs.event import EventCog
from cogs.help import HelpCog
from cogs.joined import JoinedCog
from cogs.schedule import ScheduleCog
from cogs.setup import SetupCog
from cogs.team import TeamCog
from cogs.update import UpdateCog


def get_cogs(bot):
    return [
        HelpCog(bot),
        JoinedCog(bot),
        SetupCog(bot),
        TeamCog(bot),
        ScheduleCog(bot),
        EventCog(bot),
        UpdateCog(bot)
    ]