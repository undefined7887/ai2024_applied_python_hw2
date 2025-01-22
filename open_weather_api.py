from typing import Optional
import aiohttp

from config import OPEN_WEATHER_API_TOKEN

WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


async def fetch_city_temperature(city: str) -> Optional[float]:
    async with aiohttp.ClientSession() as session:
        async with session.get(WEATHER_URL,
                               params={"q": city, "appid": OPEN_WEATHER_API_TOKEN, "units": "metric"}) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()

            return data["main"]["temp"]
