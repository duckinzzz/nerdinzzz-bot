"""Weather tool — Open-Meteo (free, no API key, metric units)."""

from __future__ import annotations

import aiohttp

from utils.logging_utils import logger

from .base import Tool

# ── WMO weather codes → Russian ────────────────────────────────────────
_WMO_CODES: dict[int, str] = {
    0: "ясно ☀️",
    1: "преимущественно ясно 🌤",
    2: "переменная облачность ⛅",
    3: "пасмурно ☁️",
    45: "туман 🌫",
    48: "изморозь ❄️",
    51: "мелкая морось 🌧",
    53: "морось 🌧",
    55: "сильная морось 🌧",
    56: "ледяная морось 🌨",
    57: "сильная ледяная морось 🌨",
    61: "небольшой дождь 🌦",
    63: "дождь 🌧",
    65: "сильный дождь 🌧",
    66: "ледяной дождь 🌨",
    67: "сильный ледяной дождь 🌨",
    71: "небольшой снег 🌨",
    73: "снег ❄️",
    75: "сильный снег ❄️",
    77: "снежные зёрна ❄️",
    80: "ливень 🌧",
    81: "сильный ливень 🌧",
    82: "очень сильный ливень 🌧",
    85: "небольшой снегопад ❄️",
    86: "сильный снегопад ❄️",
    95: "гроза ⛈",
    96: "гроза с градом ⛈",
    99: "сильная гроза с градом ⛈",
}


def _weather_code_desc(code: int) -> str:
    return _WMO_CODES.get(code, f"код {code}")


# ── Open-Meteo API calls ───────────────────────────────────────────────
_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


async def _geocode(city: str) -> dict | None:
    """Resolve city name → {lat, lon, name, country}."""
    params: dict[str, str | int] = {
        "name": city,
        "count": 1,
        "language": "ru",
        "format": "json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _GEOCODING_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    logger.warning("Open-Meteo geocoding returned %s for '%s'", resp.status, city)
                    return None
                data: dict = await resp.json()
                results = data.get("results")
                if not results:
                    return None
                r = results[0]
                return {
                    "lat": float(r["latitude"]),
                    "lon": float(r["longitude"]),
                    "name": r.get("name", city),
                    "country": r.get("country", ""),
                }
    except Exception as e:
        logger.warning("Open-Meteo geocoding error for '%s': %s", city, e)
        return None


async def _get_forecast(lat: float, lon: float) -> dict | None:
    """Fetch current weather + daily forecast from Open-Meteo."""
    params: dict[str, str | int | float] = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "wind_speed_10m,wind_direction_10m,weather_code,precipitation"
        ),
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,weather_code"
        ),
        "timezone": "auto",
        "forecast_days": 2,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _FORECAST_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status != 200:
                    logger.warning("Open-Meteo forecast returned %s", resp.status)
                    return None
                return await resp.json()
    except Exception as e:
        logger.warning("Open-Meteo forecast error: %s", e)
        return None


# ── Public tool handler ────────────────────────────────────────────────
async def get_weather(city: str) -> str:
    """Return a human-readable weather summary for the given city."""
    geo = await _geocode(city)
    if not geo:
        return f"❌ Не удалось найти город «{city}». Проверьте название."

    forecast = await _get_forecast(geo["lat"], geo["lon"])
    if not forecast:
        return f"❌ Не удалось получить прогноз для {geo['name']}."

    current = forecast.get("current", {})
    daily = forecast.get("daily", {})

    # Current weather
    temp = current.get("temperature_2m", "?")
    feels = current.get("apparent_temperature", "?")
    humidity = current.get("relative_humidity_2m", "?")
    wind = current.get("wind_speed_10m", "?")
    code = current.get("weather_code", 0)

    # Today's forecast
    temp_max = daily.get("temperature_2m_max", ["?"])[0] if daily.get("temperature_2m_max") else "?"
    temp_min = daily.get("temperature_2m_min", ["?"])[0] if daily.get("temperature_2m_min") else "?"
    precip_prob = daily.get("precipitation_probability_max", ["?"])[0] if daily.get("precipitation_probability_max") else "?"
    daily_code = daily.get("weather_code", [0])[0] if daily.get("weather_code") else code

    location = f"{geo['name']}, {geo['country']}" if geo.get("country") else geo["name"]

    lines = [
        f"📍 **{location}**",
        "",
        f"🌡 Сейчас: **{temp}°C** (ощущается {feels}°C)",
        f"🌤 {_weather_code_desc(int(code))}",
        f"💧 Влажность: {humidity}%",
        f"💨 Ветер: {wind} км/ч",
        "",
        f"📅 Сегодня: **{temp_min}°C … {temp_max}°C**, {_weather_code_desc(int(daily_code))}",
        f"🌧 Вероятность осадков: {precip_prob}%",
    ]

    return "\n".join(lines)


# ── Tool definition ────────────────────────────────────────────────────
weather_tool = Tool(
    name="get_weather",
    description=(
        "Get current weather and today's forecast for a city. "
        "Call this when the user asks about weather, temperature, rain, snow, wind, etc."
    ),
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name in any language (e.g. Москва, London, 北京)",
            },
        },
        "required": ["city"],
    },
    execute=get_weather,
)
