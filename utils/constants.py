import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
INVITE_LINK = os.getenv("INVITE_LINK", "N/A")


DONATION_LINK = os.getenv("DONATION_LINK", "N/A")

MAJOR_TIMEZONES = [
    "UTC", "London", "New York", "Los Angeles", "Chicago", "Denver", "Phoenix", "Toronto",
    "Mexico City", "Buenos Aires", "Rio de Janeiro", "Santiago", "Vancouver", "Honolulu",
    "Anchorage", "Paris", "Berlin", "Madrid", "Rome", "Moscow", "Istanbul", "Dubai",
    "Jerusalem", "Johannesburg", "Cairo", "Nairobi", "Mumbai", "Delhi", "Bangkok",
    "Singapore", "Hong Kong", "Shanghai", "Tokyo", "Seoul", "Sydney", "Melbourne",
    "Auckland", "Brisbane", "Perth", "Jakarta"
]

TIMEZONE_MAP = {
    "UTC": "UTC",
    "London": "Europe/London",
    "New York": "America/New_York",
    "Los Angeles": "America/Los_Angeles",
    "Chicago": "America/Chicago",
    "Denver": "America/Denver",
    "Phoenix": "America/Phoenix",
    "Toronto": "America/Toronto",
    "Mexico City": "America/Mexico_City",
    "Buenos Aires": "America/Argentina/Buenos_Aires",
    "Rio de Janeiro": "America/Sao_Paulo",
    "Santiago": "America/Santiago",
    "Vancouver": "America/Vancouver",
    "Honolulu": "Pacific/Honolulu",
    "Anchorage": "America/Anchorage",
    "Paris": "Europe/Paris",
    "Berlin": "Europe/Berlin",
    "Madrid": "Europe/Madrid",
    "Rome": "Europe/Rome",
    "Moscow": "Europe/Moscow",
    "Istanbul": "Europe/Istanbul",
    "Dubai": "Asia/Dubai",
    "Jerusalem": "Asia/Jerusalem",
    "Johannesburg": "Africa/Johannesburg",
    "Cairo": "Africa/Cairo",
    "Nairobi": "Africa/Nairobi",
    "Mumbai": "Asia/Kolkata",
    "Delhi": "Asia/Kolkata",
    "Bangkok": "Asia/Bangkok",
    "Singapore": "Asia/Singapore",
    "Hong Kong": "Asia/Hong_Kong",
    "Shanghai": "Asia/Shanghai",
    "Tokyo": "Asia/Tokyo",
    "Seoul": "Asia/Seoul",
    "Sydney": "Australia/Sydney",
    "Melbourne": "Australia/Melbourne",
    "Auckland": "Pacific/Auckland",
    "Brisbane": "Australia/Brisbane",
    "Perth": "Australia/Perth",
    "Jakarta": "Asia/Jakarta"
}