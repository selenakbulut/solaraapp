import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import requests

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
import save_weather  # noqa: E402


class FixedClock(datetime):
    fixed_time = datetime(2026, 10, 19, 13, 15)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed_time.replace(tzinfo=tz)


def count(connection, table):
    return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def main():
    original_db = PROJECT_DIR / "solar.db"
    if not original_db.is_file():
        raise FileNotFoundError("solar.db test dosyasiyla ayni klasorde bulunamadi")

    with tempfile.TemporaryDirectory() as folder:
        copied_db = Path(folder) / "solar.db"
        source = sqlite3.connect(original_db.as_uri() + "?mode=ro", uri=True)
        destination = sqlite3.connect(copied_db)
        try:
            source.backup(destination)
        finally:
            source.close()
            destination.close()

        previous_dir = Path.cwd()
        os.chdir(folder)
        try:
            connection = sqlite3.connect("solar.db")
            try:
                sites = connection.execute("""
                    SELECT id, name, tilt, azimuth
                    FROM sites
                    WHERE id IN (12, 13, 14)
                    ORDER BY id
                """).fetchall()
                before_requests = count(connection, "api_requests")
                before_forecasts = count(connection, "forecast_runs")
                before_weather = count(connection, "weather_data")
            finally:
                connection.close()

            if [site[0] for site in sites] != [12, 13, 14]:
                raise AssertionError("Saha 1, 2 ve 3 (ID 12, 13, 14) bulunamadi")

            FixedClock.fixed_time = datetime(2026, 10, 19, 13, 15)
            with patch.object(save_weather, "datetime", FixedClock), patch.object(
                save_weather.requests,
                "get",
                side_effect=AssertionError("Gereksiz API cagrisi!"),
            ) as mock_get:
                for site_id, site_name, tilt, azimuth in sites:
                    before_calls = mock_get.call_count
                    start_time, end_time = save_weather.save_weather_data(
                        site_id, tilt, azimuth
                    )
                    assert mock_get.call_count == before_calls, (
                        f"{site_name}: Veriler kayitliyken API cagrildi"
                    )
                    assert (start_time, end_time) == (
                        "2026-10-19T14:00", "2026-10-22T14:00"
                    ), f"{site_name}: Beklenmeyen tarih araligi"

                    connection = sqlite3.connect("solar.db")
                    try:
                        cached = connection.execute("""
                            SELECT COUNT(DISTINCT forecast_time)
                            FROM weather_data
                            WHERE site_id = ? AND tilt = ? AND azimuth = ?
                              AND forecast_time >= ? AND forecast_time < ?
                        """, (site_id, tilt, azimuth, start_time, end_time)).fetchone()[0]
                    finally:
                        connection.close()
                    assert cached == 72, f"{site_name}: {cached}/72 saat bulundu"
                    print(f"TEST 1 BASARILI - {site_name}: 72/72 saat onbellekte, 0 API istegi.")

                assert mock_get.call_count == 0

            FixedClock.fixed_time = datetime(2026, 10, 22, 13, 15)
            with patch.object(save_weather, "datetime", FixedClock), patch.object(
                save_weather.requests,
                "get",
                side_effect=requests.ConnectionError("Test: baglanti kesildi"),
            ) as mock_get:
                for site_id, site_name, tilt, azimuth in sites:
                    before_calls = mock_get.call_count
                    try:
                        save_weather.save_weather_data(site_id, tilt, azimuth)
                    except requests.RequestException:
                        pass
                    else:
                        raise AssertionError(f"{site_name}: Kesintide hata olusmadi")
                    assert mock_get.call_count == before_calls + 1, (
                        f"{site_name}: Beklenen API denemesi yapilmadi"
                    )

                    connection = sqlite3.connect("solar.db")
                    try:
                        latest_success = connection.execute("""
                            SELECT success FROM api_requests ORDER BY id DESC LIMIT 1
                        """).fetchone()
                    finally:
                        connection.close()
                    assert latest_success == (0,), (
                        f"{site_name}: Basarisiz API istegi kaydedilmedi"
                    )
                    print(f"TEST 2 BASARILI - {site_name}: Kesinti yakalandi, basarisiz istek loglandi.")

                assert mock_get.call_count == 3

            connection = sqlite3.connect("solar.db")
            try:
                after_requests = count(connection, "api_requests")
                after_forecasts = count(connection, "forecast_runs")
                after_weather = count(connection, "weather_data")
                failed_last_three = connection.execute("""
                    SELECT success FROM api_requests ORDER BY id DESC LIMIT 3
                """).fetchall()
            finally:
                connection.close()

            assert after_requests == before_requests + 3, "3 basarisiz API denemesi kaydedilmedi"
            assert failed_last_three == [(0,), (0,), (0,)], "Basarisiz istek loglari hatali"
            assert after_forecasts == before_forecasts, "Tahmin kayitlari degisti"
            assert after_weather == before_weather, "Hava kayitlari degisti"
            print("SONUC: 3/3 saha onbellek testi ve 3/3 saha kesinti testi BASARILI.")
            print("Gercek solar.db degistirilmedi. Gercek API istegi gonderilmedi.")
        finally:
            os.chdir(previous_dir)


if __name__ == "__main__":
    main()
