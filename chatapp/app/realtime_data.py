"""Live data for the assistant (time in any place, weather).

Privacy: the only thing that ever leaves the server is a place name the person typed, sent to the free
Open-Meteo service. Chat text, names, and conversation details are never sent. Web lookups can be turned off
with CHATAPP_COPILOT_WEB=false, and then everything here works offline except the weather.
"""
import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

log = logging.getLogger("chatapp.realtime")

WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers", 81: "rain showers",
    82: "violent rain showers", 95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}

CITY_ZONES = {
    "utc": "UTC", "gmt": "UTC", "seattle": "America/Los_Angeles", "redmond": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles", "los angeles": "America/Los_Angeles", "pst": "America/Los_Angeles",
    "pacific": "America/Los_Angeles", "denver": "America/Denver", "chicago": "America/Chicago",
    "new york": "America/New_York", "est": "America/New_York", "toronto": "America/Toronto",
    "london": "Europe/London", "dublin": "Europe/Dublin", "paris": "Europe/Paris", "berlin": "Europe/Berlin",
    "madrid": "Europe/Madrid", "rome": "Europe/Rome", "amsterdam": "Europe/Amsterdam",
    "dubai": "Asia/Dubai", "india": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "delhi": "Asia/Kolkata",
    "bangalore": "Asia/Kolkata", "bengaluru": "Asia/Kolkata", "hyderabad": "Asia/Kolkata",
    "chennai": "Asia/Kolkata", "ist": "Asia/Kolkata", "singapore": "Asia/Singapore", "tokyo": "Asia/Tokyo",
    "japan": "Asia/Tokyo", "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai", "sydney": "Australia/Sydney",
    "melbourne": "Australia/Melbourne", "auckland": "Pacific/Auckland",
}

_PLACE_OK = re.compile(r"[^A-Za-z\u00C0-\u024F ,'./_-]")


@dataclass
class WebLookup:
    kind: str  # "weather" or "time"
    place: str


def clean_place(text: str) -> str:
    text = re.sub(r"^(in|for|at|of)\s+", "", text.strip(), flags=re.I)
    return _PLACE_OK.sub("", text).strip()[:60]


class RealtimeData:
    def __init__(self, web_enabled: bool, timeout: float = 4.0):
        self.web_enabled = web_enabled
        self.timeout = timeout

    # --- offline ---------------------------------------------------------
    @staticmethod
    def format_time(tz_name: str, label: str) -> str:
        now = datetime.now(ZoneInfo(tz_name))
        return f"It is {now.strftime('%A %d %B %Y, %H:%M')} in {label} ({now.strftime('%Z')}, {tz_name})."

    def zone_for(self, place: str) -> str | None:
        key = place.strip().lower()
        if key in CITY_ZONES:
            return CITY_ZONES[key]
        try:  # an IANA name such as Asia/Kolkata
            ZoneInfo(place.strip())
            return place.strip()
        except (ZoneInfoNotFoundError, ValueError, OSError):
            return None

    # --- the web (only a place name is sent) ----------------------------------
    def _get(self, url: str) -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": "TeamChat-Copilot/1.0"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (fixed https hosts)
            return json.loads(response.read(200_000))

    def _geocode(self, place: str) -> dict | None:
        url = "https://geocoding-api.open-meteo.com/v1/search?count=1&language=en&format=json&name=" + urllib.parse.quote(place)
        results = self._get(url).get("results") or []
        return results[0] if results else None

    def run(self, lookup: WebLookup) -> str:
        """Blocking network call. The caller runs it off the event loop."""
        if not self.web_enabled:
            return "Live web data is switched off on this server."
        try:
            found = self._geocode(lookup.place)
            if not found:
                return f"I could not find a place called \"{lookup.place}\"."
            label = ", ".join(x for x in (found.get("name"), found.get("admin1"), found.get("country")) if x)
            if lookup.kind == "time":
                return self.format_time(found["timezone"], label)
            url = ("https://api.open-meteo.com/v1/forecast?current=temperature_2m,apparent_temperature,"
                   "relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto"
                   f"&latitude={found['latitude']}&longitude={found['longitude']}")
            current = self._get(url)["current"]
            sky = WEATHER_CODES.get(current.get("weather_code"), "unsettled weather")
            return (f"Weather now in {label}: {current['temperature_2m']} C (feels like {current['apparent_temperature']} C), "
                    f"{sky}, humidity {current['relative_humidity_2m']} percent, wind {current['wind_speed_10m']} km/h. "
                    f"Live data from Open-Meteo, observed {current['time'].replace('T', ' ')} local time.")
        except Exception as exc:  # network down, timeout, bad reply
            log.warning("web_lookup_failed", extra={"event": "web_lookup_failed", "code": type(exc).__name__})
            return "I could not reach the live data service just now. Please try again in a moment."
