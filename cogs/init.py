from cogs.event import EventCog
from cogs.games import GamesCog
from cogs.help import HelpCog
from cogs.joined import JoinedCog
from cogs.schedule import ScheduleCog
from cogs.scrim import ScrimCog
from cogs.setup import SetupCog
from cogs.status import StatusCog
from cogs.team import TeamCog
from cogs.update import UpdateCog


def get_cogs(bot):
    return [
        HelpCog(bot),
        JoinedCog(bot),
        SetupCog(bot),
        StatusCog(bot),
        TeamCog(bot),
        GamesCog(bot),
        ScheduleCog(bot),
        EventCog(bot),
        ScrimCog(bot),
        UpdateCog(bot)
    ]