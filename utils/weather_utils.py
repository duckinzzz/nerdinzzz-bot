"""Weather data via MCP weather server + Nominatim geocoder.

Геокодинг через OpenStreetMap Nominatim (понимает города на любом языке),
прогноз погоды через MCP сервер weather-mcp.

Держит одно MCP-соединение на весь цикл бота.
"""

import asyncio
import re
from typing import Any

import aiohttp

from core.config import MCP_WEATHER_COMMAND, MCP_WEATHER_ARGS
from utils.logging_utils import logger
from utils.mcp_client import McpClient, McpError

# ── Геокодинг через Nominatim (OSM, бесплатно, без API-ключа) ──────
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


async def _geocode(query: str) -> dict[str, Any] | None:
    """Геокодирует название населённого пункта через Nominatim.

    Поддерживает любые языки — кириллица, латиница, арабица,
    китайские иероглифы и т.д. Возвращает координаты и название.
    """
    headers = {"User-Agent": "nerdinzzz-bot/1.0"}
    params = {"q": query, "format": "json", "limit": 5}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                _NOMINATIM_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    logger.warning("Nominatim returned %s for '%s'", resp.status, query)
                    return None
                data = await resp.json()
                if not data:
                    # Не нашли — попробуем с нормализованным окончанием
                    normalized = _normalize_russian_ending(query)
                    if normalized != query and len(normalized) >= 2:
                        logger.debug("Retry with normalized: '%s'", normalized)
                        return await _geocode(normalized)
                    return None

                # Ищем первый результат — населённый пункт, а не адрес
                preferred = {"city", "town", "village", "administrative"}
                # Сначала ищем по addresstype
                for r in data:
                    if r.get("addresstype") in preferred:
                        return _pick_result(r)
                # Затем пробуем по category=place (любой населённый пункт)
                for r in data:
                    if r.get("category") == "place":
                        return _pick_result(r)
                # Всё остальное — берём первый результат как есть
                return _pick_result(data[0])
    except asyncio.TimeoutError:
        logger.warning("Nominatim timeout for '%s'", query)
        return None
    except Exception as e:
        logger.warning("Nominatim error for '%s': %s", query, e)
        return None


def _pick_result(r: dict[str, Any]) -> dict[str, Any]:
    """Извлекает lat/lon/name из ответа Nominatim."""
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "name": _friendly_name(r),
    }


def _friendly_name(result: dict[str, Any]) -> str:
    """Вытаскивает короткое название города из ответа Nominatim."""
    # Поле name есть в Nominatim — это чистое название объекта
    name = result.get("name")
    if name and isinstance(name, str) and len(name) >= 2:
        return name
    # Если нет name — берём первую часть display_name
    display = result.get("display_name", "")
    first = display.split(",")[0].strip()
    return first or display


def _normalize_russian_ending(name: str) -> str:
    """Убирает типичные падежные окончания русских городов.

    Пользователи пишут 'во владивостоке', 'в москве', 'в лондоне' —
    а Nominatim лучше находит 'владивосток', 'москва', 'лондон'.
    """
    if not re.search(r'[а-яё]', name):
        return name

    # Предложный падеж: -е (владивостоке, лондоне, париже, берлине)
    # Родительный: -а/-я (ищу до москвы → москв... не надо, слишком грубо)
    # Ограничимся безопасным: убираем конечное -е
    if name.endswith("е") and len(name) > 4:
        candidate = name[:-1]
        if len(candidate) >= 3:
            return candidate

    return name


# ── Конвертация единиц (сервер всегда отдаёт °F/mph/in) ────────────

def _to_metric(text: str) -> str:
    """Переводит °F→°C, mph→м/с, inches→мм в тексте прогноза."""
    def _f_to_c(m: re.Match) -> str:
        f = float(m.group(1))
        c = round((f - 32) * 5 / 9)
        return f"{c}°C"

    def _mph_to_ms(m: re.Match) -> str:
        mph = float(m.group(1))
        ms = round(mph * 0.44704, 1)
        return f"{ms} m/s"

    def _in_to_mm(m: re.Match) -> str:
        inches = float(m.group(1))
        mm = round(inches * 25.4, 1)
        return f"{mm} mm"

    text = re.sub(r"(-?\d+(?:\.\d+)?)°F", _f_to_c, text)
    text = re.sub(r"(-?\d+(?:\.\d+)?) mph", _mph_to_ms, text)
    text = re.sub(r"(-?\d+(?:\.\d+)?) in\b", _in_to_mm, text)
    # Переименовываем заголовки полей для ясности
    text = text.replace("**Temperature:**", "**Temperature (°C):**")
    text = text.replace("**Feels Like:**", "**Feels Like (°C):**")
    text = text.replace("**Wind:**", "**Wind (m/s):**")
    text = text.replace("**Wind Gusts:**", "**Wind Gusts (m/s):**")
    text = text.replace("**Precipitation:**", "**Precipitation (mm):**")
    return text


# ── Детекция погодного запроса ──────────────────────────────────────
WEATHER_KEYWORDS: set[str] = {
    "погода", "weather",
    "температура", "temperature",
    "прогноз", "forecast",
    "дождь", "rain", "rainy",
    "снег", "snow", "snowy",
    "ветер", "wind", "windy",
    "гроза", "storm", "thunderstorm",
    "туман", "fog", "foggy",
    "облачно", "cloudy", "clouds",
    "солнечно", "sunny", "sun",
    "град", "hail",
    "гололёд", "ice", "мороз", "frost",
    "влажность", "humidity",
    "давление", "pressure",
}


def is_weather_query(text: str) -> bool:
    """Проверяет, похож ли текст на запрос о погоде."""
    return any(kw in text.lower() for kw in WEATHER_KEYWORDS)


# ── Извлечение города из текста ─────────────────────────────────────
def extract_location(text: str) -> str | None:
    """Извлекает название населённого пункта из запроса о погоде."""
    text_lower = text.lower().strip()

    # \w в Python 3 включает любую Unicode-букву, так что города
    # на китайском, арабском, японском и т.д. тоже подхватятся.
    patterns = [
        # После предлогов: в/во/на/у/для/in/for
        r"(?:в|во|на|у|для|in|for)\s([\w-][\w\s-]{0,30}?)(?:\?|\,|\.|\!|\s|$)",
        # Сразу после ключевого слова: "погода москва"
        r"(?:погода|weather|forecast|прогноз)\s+(?:в |во |на |для |in |for )?([\w-][\w\s-]{0,30}?)(?:\?|\,|\.|\!|\s|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            location = match.group(1).strip()
            location = re.sub(r"[?.,!;:\"']+$", "", location).strip()
            if location and len(location) >= 2:
                return location
    return None


# ── Постоянное MCP-соединение (один раз стартуем, живёт всё время) ─
_mcp_instance: McpClient | None = None
_mcp_lock = asyncio.Lock()


async def _ensure_mcp() -> McpClient:
    """Возвращает единственный экземпляр MCP-клиента, создавая при
    необходимости. При обрыве переподключается."""
    global _mcp_instance

    # Проверяем живо ли соединение (лёгкий no-op запрос)
    if _mcp_instance is not None:
        try:
            await _mcp_instance.call_tool("check_service_status")
            return _mcp_instance
        except McpError:
            logger.info("MCP connection lost, restarting...")
            await _mcp_instance.stop()
            _mcp_instance = None

    async with _mcp_lock:
        if _mcp_instance is not None:
            return _mcp_instance
        client = McpClient(MCP_WEATHER_COMMAND, MCP_WEATHER_ARGS)
        await client.start()
        _mcp_instance = client
    return _mcp_instance


async def stop_mcp() -> None:
    """Закрывает MCP-соединение (вызвать на shutdown бота)."""
    global _mcp_instance
    if _mcp_instance is not None:
        await _mcp_instance.stop()
        _mcp_instance = None


# ── Главная функция ─────────────────────────────────────────────────
async def get_weather_for_query(text: str) -> str | None:
    """Полный пайплайн: локация → координаты → прогноз.

    Args:
        text: Текст запроса пользователя.

    Returns:
        Строку вида "📍 Moscow: ..." для вставки в контекст LLM, или None.
    """
    location = extract_location(text)
    if not location:
        return None

    logger.debug("Weather query: location='%s'", location)

    try:
        # Шаг 1: геокодим через Nominatim (понимает любой язык)
        geo = await _geocode(location)
        if not geo:
            logger.info("No geocoding result for '%s'", location)
            return None

        logger.debug("Geocoded '%s' -> (%s, %s) as '%s'", location, geo["lat"], geo["lon"], geo["name"])

        mcp = await _ensure_mcp()

        # Шаг 2: прогноз по координатам
        forecast = await mcp.call_tool("get_forecast", {
            "latitude": geo["lat"],
            "longitude": geo["lon"],
        })

        if not forecast:
            return None

        forecast = forecast.strip()
        forecast = _to_metric(forecast)
        logger.debug("Forecast for '%s': %s...", geo["name"], forecast[:100])
        return f"📍 {geo['name']}: {forecast}"

    except McpError as e:
        logger.warning("MCP weather failed for '%s': %s", location, e)
        return None
    except Exception as e:
        logger.warning("Unexpected error getting weather for '%s': %s", location, e)
        return None
