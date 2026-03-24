from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from urllib.parse import urlencode
from urllib.request import urlopen



logger = logging.getLogger("ai_weather")


class WeatherClient:
    """Cliente simples para previsão de clima com Open-Meteo."""

    async def get_forecast_score(self, *, lat: float, lon: float) -> float:
        """
        Retorna score [0..1] de favorabilidade para visitas.
        Heurística: menos chuva prevista e temperatura moderada elevam o score.
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "precipitation,temperature_2m",
            "forecast_days": 2,
            "timezone": "auto",
        }
        try:
            query = urlencode(params)
            endpoint = f"{url}?{query}"

            def _fetch() -> dict:
                with urlopen(endpoint, timeout=8) as response:
                    return json.loads(response.read().decode("utf-8"))

            data = await asyncio.to_thread(_fetch)
        except Exception as exc:
            logger.warning("Falha ao consultar clima: %s", exc)
            return 0.5

        hourly = data.get("hourly", {})
        precip = hourly.get("precipitation", [])
        temps = hourly.get("temperature_2m", [])

        if not precip or not temps:
            return 0.5

        rain_penalty = min(sum(float(v or 0) for v in precip[:24]) / 24.0, 3.0) / 3.0
        temp_values = [float(v or 0) for v in temps[:24]]
        avg_temp = sum(temp_values) / max(len(temp_values), 1)

        # Ideal agrícola operacional: 18-28C.
        temp_score = max(0.0, 1.0 - abs(avg_temp - 23.0) / 20.0)
        weather_score = max(0.0, min(1.0, (1.0 - rain_penalty) * 0.6 + temp_score * 0.4))
        return weather_score

    @staticmethod
    def next_best_hour_label() -> str:
        now = datetime.now()
        return f"{(now.hour + 2) % 24:02d}:00"
