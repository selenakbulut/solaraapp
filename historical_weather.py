import math
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_FIELDS = (
    "temperature_2m",
    "wind_speed_10m",
    "cloud_cover",
    "shortwave_radiation",
    "global_tilted_irradiance",
)


def _expected_hours(start_date, end_date):
    current = datetime.combine(start_date, datetime.min.time())
    last = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
    hours = []
    while current < last:
        hours.append(current.strftime("%Y-%m-%dT%H:%M"))
        current += timedelta(hours=1)
    return hours


def _prepare_cache(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS historical_weather_data (
            site_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            weather_time TEXT NOT NULL,
            temperature REAL NOT NULL,
            wind_speed REAL NOT NULL,
            cloud_cover REAL NOT NULL,
            shortwave_radiation REAL NOT NULL,
            tilted_radiation REAL NOT NULL,
            tilt REAL NOT NULL,
            azimuth REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (site_id, latitude, longitude, weather_time, tilt, azimuth),
            FOREIGN KEY (site_id) REFERENCES sites(id)
        )
    """)
    connection.commit()


def _valid_archive_hours(data, expected):
    hourly = data.get("hourly")
    if not isinstance(hourly, dict) or hourly.get("time") != expected:
        raise ValueError("Tarihsel API saatleri istenen aralikla eslesmiyor.")

    for field in HOURLY_FIELDS:
        values = hourly.get(field)
        if not isinstance(values, list) or len(values) != len(expected):
            raise ValueError(f"Tarihsel API alanı eksik veya hatali: {field}")
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in values
        ):
            raise ValueError(f"Tarihsel API gecersiz veri dondurdu: {field}")
    return hourly


def get_historical_weather(site_id, start_date, end_date, db_path="solar.db",
                           azimuth_override=None, tilt_override=None,
                           latitude_override=None, longitude_override=None ):
    start_date = date.fromisoformat(str(start_date))
    end_date = date.fromisoformat(str(end_date))
    if end_date < start_date:
        raise ValueError("Bitis tarihi baslangictan once olamaz.")

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        row = connection.execute("""
            SELECT name, latitude, longitude, tilt, azimuth, timezone
            FROM sites WHERE id = ?
        """, (site_id,)).fetchone()
        if row is None:
            raise ValueError(f"Santral bulunamadi: {site_id}")
        name, lat, lon, tilt, azimuth, site_timezone = row

        if tilt_override is not None:
            if not 0 <= tilt_override <= 90:
                raise ValueError("Panel eğimi 0 ile 90 arasında olmalıdır.")

            tilt = tilt_override

        if azimuth_override is not None:
            if not -180 <= azimuth_override <= 180:
                raise ValueError("Azimut -180 ile 180 arasında olmalıdır.")

            azimuth = azimuth_override

        if (latitude_override is None) != (longitude_override is None):
            raise ValueError("Enlem ve boylam birlikte verilmelidir.")

        if latitude_override is not None:
            lat = float(latitude_override)
            lon = float(longitude_override)

            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("Gecersiz koordinatlar.")

        if not site_timezone:
            raise ValueError(f"Santralin saat dilimi kayitli degil: {name}")
        if end_date >= datetime.now(ZoneInfo(site_timezone)).date():
            raise ValueError("Tarihsel veri icin gecmiste tamamlanmis gunler secilmeli.")

        _prepare_cache(connection)
        expected = _expected_hours(start_date, end_date)
        first, last = expected[0], expected[-1]
        present = {
            item[0] for item in connection.execute("""
                SELECT weather_time FROM historical_weather_data
                WHERE site_id = ? AND latitude = ? AND longitude = ?
                  AND tilt = ? AND azimuth = ?
                  AND weather_time >= ? AND weather_time <= ?
            """, (site_id, lat, lon, tilt, azimuth, first, last))
        }

        if len(present) == len(expected) and present == set(expected):
            print(f"{name}: {len(expected)}/{len(expected)} saat SQLite'tan; 0 API istegi.")
            return len(expected)

        limit = int(os.getenv("SOLAR_DAILY_API_LIMIT", "50"))
        turkey_now = datetime.now(ZoneInfo("Europe/Istanbul"))
        day_start = turkey_now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        used = connection.execute("""
            SELECT COUNT(*) FROM api_requests
            WHERE requested_at >= ? AND requested_at < ?
        """, (day_start.astimezone(timezone.utc).isoformat(),
              day_end.astimezone(timezone.utc).isoformat())).fetchone()[0]
        if limit < 0 or used >= limit:
            raise RuntimeError(f"Gunluk API istek limiti dolu: {used}/{limit}")

        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": ",".join(HOURLY_FIELDS),
            "tilt": tilt,
            "azimuth": azimuth,
            "timezone": site_timezone,
        }
        requested_at = datetime.now(timezone.utc).isoformat()
        status_code = None
        success = 0
        rows = []
        print(f"{name}: {len(present)}/{len(expected)} saat onbellekte; "
              f"eksik saatler icin 1 tarihsel API istegi.")
        try:
            response = requests.get(ARCHIVE_URL, params=params, timeout=30)
            status_code = response.status_code
            response.raise_for_status()
            hourly = _valid_archive_hours(response.json(), expected)
            fetched_at = datetime.now(timezone.utc).isoformat()
            for i, hour in enumerate(expected):
                if hour not in present:
                    rows.append((
                        site_id, lat, lon, hour,
                        float(hourly["temperature_2m"][i]),
                        float(hourly["wind_speed_10m"][i]),
                        float(hourly["cloud_cover"][i]),
                        float(hourly["shortwave_radiation"][i]),
                        float(hourly["global_tilted_irradiance"][i]),
                        tilt, azimuth, fetched_at,
                    ))
            success = 1
        finally:
            connection.execute("""
                INSERT INTO api_requests(requested_at, endpoint, status_code, success)
                VALUES (?, ?, ?, ?)
            """, (requested_at, ARCHIVE_URL, status_code, success))
            if success:
                connection.executemany("""
                    INSERT OR IGNORE INTO historical_weather_data (
                        site_id, latitude, longitude, weather_time,
                        temperature, wind_speed, cloud_cover,
                        shortwave_radiation, tilted_radiation,
                        tilt, azimuth, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, rows)
            connection.commit()

        final_count = connection.execute("""
            SELECT COUNT(*) FROM historical_weather_data
            WHERE site_id = ? AND latitude = ? AND longitude = ?
              AND tilt = ? AND azimuth = ?
              AND weather_time >= ? AND weather_time <= ?
        """, (site_id, lat, lon, tilt, azimuth, first, last)).fetchone()[0]
        if final_count != len(expected):
            raise RuntimeError(f"{name}: Veri eksik ({final_count}/{len(expected)}).")
        print(f"{name}: {final_count}/{len(expected)} saat kaydedildi.")
        return final_count


if __name__ == "__main__":

    with sqlite3.connect("solar.db") as connection:
        sites = connection.execute("""
            SELECT id, name
            FROM sites
            ORDER BY id
        """).fetchall()

    print("\nKAYITLI SANTRALLER")
    print("-" * 40)

    for site_id, site_name in sites:
        print(f"{site_id} - {site_name}")

    print("0 - Tum santraller")

    selected_id = int(input("\nSantral ID secin: "))

    start_date = input("Baslangic tarihi (YYYY-MM-DD): ").strip()
    end_date = input("Bitis tarihi (YYYY-MM-DD): ").strip()

    if selected_id == 0:
        selected_sites = sites
    else:
        selected_sites = [
            site for site in sites if site[0] == selected_id
        ]

        if not selected_sites:
            raise ValueError("Gecersiz santral ID.")

    for site_id, site_name in selected_sites:
        print(f"\nKontrol edilen santral: {site_name}")

        get_historical_weather(
            site_id,
            start_date,
            end_date
        )

    print("\nBITTI: Gecmis hava verileri kontrol edildi.")
