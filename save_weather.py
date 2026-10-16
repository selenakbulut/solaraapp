import sqlite3
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def save_weather_data(site_id, tilt, azimuth):
    now = datetime.now(ZoneInfo("Europe/Istanbul"))

    start = now.replace(
        minute=0,
        second=0,
        microsecond=0
    ) + timedelta(hours=1)

    end = start + timedelta(hours=72)

    start_time = start.strftime("%Y-%m-%dT%H:%M")
    end_time = end.strftime("%Y-%m-%dT%H:%M")

    print("Tahmin başlangıcı:", start_time)
    print("Tahmin bitişi:", end_time)

    connection = sqlite3.connect("solar.db")
    connection.execute("PRAGMA foreign_keys = ON")
    cursor = connection.cursor()

    cursor.execute("""
        SELECT name, latitude, longitude
        FROM sites
        WHERE id = ?
    """, (site_id,))

    site = cursor.fetchone()

    if site is None:
        connection.close()
        raise ValueError("Santral bulunamadı.")

    site_name, latitude, longitude = site

    print("Seçilen santral:", site_name)
    print("Koordinatlar:", latitude, longitude)

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    expected_times = []
    current = start

    while current < end:
        expected_times.append(current.strftime("%Y-%m-%dT%H:%M"))
        current += timedelta(hours=1)

    cursor.execute("""
        INSERT OR IGNORE INTO weather_data (
            site_id, forecast_time, temperature, wind_speed,
            cloud_cover, shortwave_radiation, tilted_radiation,
            tilt, azimuth, fetched_at
        )
        SELECT
            ?, w.forecast_time, w.temperature, w.wind_speed,
            w.cloud_cover, w.shortwave_radiation, w.tilted_radiation,
            w.tilt, w.azimuth, w.fetched_at
        FROM weather_data AS w
        JOIN sites AS s ON s.id = w.site_id
        WHERE s.latitude = ?
          AND s.longitude = ?
          AND w.tilt = ?
          AND w.azimuth = ?
          AND w.forecast_time >= ?
          AND w.forecast_time < ?
          AND w.site_id != ?
    """, (
        site_id, latitude, longitude, tilt, azimuth,
        start_time, end_time, site_id
    ))

    print("Diğer santrallerden kopyalanan saat sayısı:", cursor.rowcount)
    connection.commit()

    cursor.execute("""
        SELECT forecast_time
        FROM weather_data
        WHERE site_id = ?
          AND tilt = ?
          AND azimuth = ?
          AND forecast_time >= ?
          AND forecast_time < ?
    """, (site_id, tilt, azimuth, start_time, end_time))

    existing_times = {row[0] for row in cursor.fetchall()}
    missing_times = [hour for hour in expected_times if hour not in existing_times]

    print("İstenen saat sayısı:", len(expected_times))
    print("Kayıtlı saat sayısı:", len(existing_times))
    print("Eksik saat sayısı:", len(missing_times))

    if not missing_times:
        print("Veriler SQLite'ta mevcut.")
        print("Yeni API isteği gönderilmedi.")

    else:
        print("Eksik veriler için API isteği gönderiliyor.")

        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": [
                "temperature_2m",
                "wind_speed_10m",
                "cloud_cover",
                "shortwave_radiation",
                "global_tilted_irradiance"
            ],
            "tilt": tilt,
            "azimuth": azimuth,
            "timezone": "Europe/Istanbul",
            "start_date": start.date().isoformat(),
            "end_date": (end - timedelta(hours=1)).date().isoformat()
        }

        requested_at = datetime.now(timezone.utc).isoformat()
        status_code = None
        success = 0

        try:
            response = requests.get(url, params=params, timeout=10)
            status_code = response.status_code
            response.raise_for_status()
            success = 1

        except requests.RequestException as error:
            status_code = (
                error.response.status_code
                if error.response is not None
                else None
            )
            success = 0
            print("API isteği başarısız:", error)
            raise

        finally:
            cursor.execute("""
                INSERT INTO api_requests (requested_at, endpoint, status_code, success)
                VALUES (?, ?, ?, ?)
        """, (requested_at, url, status_code, success))

            connection.commit()

        hourly = response.json()["hourly"]
        fetched_at = datetime.now(timezone.utc).isoformat()
        saved_count = 0

        for i, forecast_time in enumerate(hourly["time"]):
            if forecast_time not in missing_times:
                continue

            cursor.execute("""
                INSERT OR IGNORE INTO weather_data (
                    site_id, forecast_time, temperature, wind_speed,
                    cloud_cover, shortwave_radiation, tilted_radiation,
                    tilt, azimuth, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                site_id,
                forecast_time,
                hourly["temperature_2m"][i],
                hourly["wind_speed_10m"][i],
                hourly["cloud_cover"][i],
                hourly["shortwave_radiation"][i],
                hourly["global_tilted_irradiance"][i],
                tilt,
                azimuth,
                fetched_at
            ))
            saved_count += cursor.rowcount

        connection.commit()
        print("Yeni kaydedilen saat sayısı:", saved_count)

    connection.close()
    return start_time, end_time


if __name__ == "__main__":
    save_weather_data(1, 90, 0)