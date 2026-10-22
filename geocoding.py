import os
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def get_coordinates(location_name: str):
    query_name = location_name.strip().casefold()

    if len(query_name) < 2:
        raise ValueError("En az iki karakterlik konum adı girin.")

    connection = sqlite3.connect("solar.db")

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                display_name,
                latitude,
                longitude,
                elevation,
                timezone
            FROM geocoding_cache
            WHERE query_name = ?
        """, (query_name,))

        cached = cursor.fetchone()

        if cached is not None:
            print("Konum SQLite'tan alindi. API istegi yok.")

            return {
                "name": cached[0],
                "latitude": cached[1],
                "longitude": cached[2],
                "elevation": cached[3],
                "timezone": cached[4]
            }

        daily_limit = int(
            os.getenv("SOLAR_DAILY_API_LIMIT", "50")
        )

        if daily_limit < 0:
            raise ValueError("API istek siniri negatif olamaz.")

        now = datetime.now(ZoneInfo("Europe/Istanbul"))
        day_start = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)

        cursor.execute("""
            SELECT COUNT(*)
            FROM api_requests
            WHERE requested_at >= ?
              AND requested_at < ?
        """, (
            day_start.astimezone(timezone.utc).isoformat(),
            day_end.astimezone(timezone.utc).isoformat()
        ))

        if cursor.fetchone()[0] >= daily_limit:
            raise requests.RequestException(
                "Gunluk API istek sinirina ulasildi."
            )

        requested_at = datetime.now(timezone.utc).isoformat()
        status_code = None
        success = 0

        try:
            response = requests.get(
                GEOCODING_URL,
                params={
                    "name": location_name.strip(),
                    "count": 1,
                    "language": "tr",
                    "format": "json"
                },
                timeout=10
            )

            status_code = response.status_code
            response.raise_for_status()
            data = response.json()
            success = 1

        finally:
            cursor.execute("""
                INSERT INTO api_requests (
                    requested_at, endpoint, status_code, success
                )
                VALUES (?, ?, ?, ?)
            """, (
                requested_at,
                GEOCODING_URL,
                status_code,
                success
            ))
            connection.commit()

        results = data.get("results", [])

        if not results:
            return None

        place = results[0]

        result = {
            "name": place["name"],
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "elevation": place.get("elevation"),
            "timezone": place.get("timezone")
        }

        cursor.execute("""
            INSERT INTO geocoding_cache (
                query_name,
                display_name,
                latitude,
                longitude,
                elevation,
                timezone,
                fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            query_name,
            result["name"],
            result["latitude"],
            result["longitude"],
            result["elevation"],
            result["timezone"],
            datetime.now(timezone.utc).isoformat()
        ))

        connection.commit()

        return result

    finally:
        connection.close()
