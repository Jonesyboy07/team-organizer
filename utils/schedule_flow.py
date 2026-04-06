from datetime import timedelta

import discord


def get_previous_monday(dt):
    return dt - timedelta(days=dt.weekday())


def get_number_emojis():
    return ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def build_day_message(date_str):
    return f"**{date_str}**"


class WeeklyScheduleIntroView(discord.ui.LayoutView):
    def __init__(self, team_role_mention: str, start_date):
        super().__init__(timeout=60)
        number_emojis = get_number_emojis()
        time_labels = [
            "1 PM", "2 PM", "3 PM", "4 PM", "5 PM", "6 PM",
            "7 PM", "8 PM", "9 PM", "10 PM",
        ]
        times_str = "\\n".join([f"{emoji} = {label}" for emoji, label in zip(number_emojis, time_labels)])

        container = discord.ui.Container(accent_color=discord.Color.blue())
        container.add_item(discord.ui.TextDisplay("## Weekly Scheduling"))
        container.add_item(
            discord.ui.TextDisplay(
                (
                    f"{team_role_mention}\\n"
                    f"**{start_date.strftime('%A: The %d of %B')}**\\n\\n"
                    "Scheduling for this week!\\n"
                    "Each day will have a message for you to react to.\\n"
                    "Time slots run from **1 PM to 10 PM**.\\n"
                    f"React with the emojis below:\\n\\n{times_str}"
                )
            )
        )
        container.add_item(discord.ui.TextDisplay("-# React to each day to indicate your availability."))
        self.add_item(container)


async def send_weekly_schedule_messages(channel, team_role_mention, start_date):
    await channel.send(view=WeeklyScheduleIntroView(team_role_mention, start_date))

    number_emojis = get_number_emojis()
    for i in range(7):
        day_date = start_date + timedelta(days=i)
        day_str = day_date.strftime("%A: The %d of %B")
        msg_content = build_day_message(day_str)
        message = await channel.send(msg_content)
        for emoji in number_emojis:
            await message.add_reaction(emoji)
