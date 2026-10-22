import argparse
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from solar_model import calculate_production

SITE_IDS = (12, 13, 14)
LOSS_COLUMNS = (
    "soiling_loss", "reflection_loss", "mismatch_loss", "dc_cable_loss",
    "ac_cable_loss", "transformer_loss", "shading_loss",
    "availability_loss", "snow_loss",
)


def run(db_path, start_day, end_day, hourly=False):
    start = datetime.strptime(start_day, "%Y-%m-%d")
    end = datetime.strptime(end_day, "%Y-%m-%d")
    if end < start:
        raise ValueError("Bitis tarihi baslangictan once olamaz.")

    expected_hours = []
    t = start
    while t < end + timedelta(days=1):
        expected_hours.append(t.strftime("%Y-%m-%dT%H:%M"))
        t += timedelta(hours=1)

    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise FileNotFoundError(f"Veritabani bulunamadi: {db_path}")

    with sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True) as connection:
        available = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='historical_weather_data'"
        ).fetchone()
        if not available:
            raise RuntimeError("historical_weather_data tablosu yok. Once historical_weather.py calistirilmali.")

        print(f"DONEM: {start_day} - {end_day} ({len(expected_hours)} saat/saha)")
        print("KAYNAK: SQLite tarihsel hava verileri. Yeni API istegi: 0.")
        print("NOT: Bunlar geriye donuk MODEL hesaplaridir, gercek uretim degildir.\n")

        for site_id in SITE_IDS:
            site = connection.execute("""
                SELECT name, latitude, longitude, tilt, azimuth,
                       panel_count, panel_power_wp, ac_power_kw, site_age_years
                FROM sites WHERE id = ?
            """, (site_id,)).fetchone()
            if site is None:
                raise RuntimeError(f"Santral ID {site_id} bulunamadi.")

            (name, lat, lon, tilt, azimuth, panel_count, wp, ac_kw, age) = site
            if any(v is None for v in (panel_count, wp, ac_kw, age)):
                raise RuntimeError(f"{name}: Santral teknik parametreleri eksik.")

            values = connection.execute("""
                SELECT weather_time, temperature, tilted_radiation
                FROM historical_weather_data
                WHERE site_id = ? AND latitude = ? AND longitude = ?
                  AND tilt = ? AND azimuth = ?
                  AND weather_time >= ? AND weather_time <= ?
                ORDER BY weather_time
            """, (site_id, lat, lon, tilt, azimuth, expected_hours[0], expected_hours[-1])).fetchall()
            times = [row[0] for row in values]
            if times != expected_hours:
                raise RuntimeError(
                    f"{name}: {len(values)}/{len(expected_hours)} saat bulundu. "
                    "Once tarihi hava verilerini eksiksiz kaydedin."
                )

            loss_row = connection.execute(
                "SELECT " + ", ".join(LOSS_COLUMNS) + " FROM site_losses WHERE site_id = ?",
                (site_id,)
            ).fetchone()
            losses = dict(zip(LOSS_COLUMNS, loss_row)) if loss_row else {}
            dc_kwp = float(panel_count) * float(wp) / 1000
            daily = defaultdict(lambda: {"energy": 0.0, "clipping": 0.0, "peak": 0.0, "hours": 0})
            total = 0.0

            print(f"{name} (ID {site_id}) | DC {dc_kwp:.2f} kWp | AC {ac_kw:.2f} kW | "
                  f"Kayiplar: {'ozel saha katsayilari' if losses else 'varsayilan DC %5 / AC %2'}")
            print("Tarih       | Saat | Toplam (kWh) | Tepe (kW) | Kirpma (kWh)")
            print("-" * 64)
            for hour, temperature, radiation in values:
                if temperature is None or radiation is None or not all(
                    math.isfinite(float(v)) for v in (temperature, radiation)
                ):
                    raise RuntimeError(f"{name}, {hour}: gecersiz hava verisi.")
                energy, clipping = calculate_production(
                    radiation=float(radiation),
                    air_temp=float(temperature),
                    dc_power_kwp=dc_kwp,
                    inverter_power_kw=float(ac_kw),
                    panel_age_years=float(age),
                    **losses,
                )
                if hourly:
                    print(f"   {hour} | Enerji {energy:.2f} kWh | Kirpma {clipping:.2f} kWh")
                day = daily[hour[:10]]
                day["energy"] += energy
                day["clipping"] += clipping
                day["peak"] = max(day["peak"], energy)
                day["hours"] += 1
                total += energy

            for day_label, v in sorted(daily.items()):
                print(f"{day_label} | {v['hours']:>4} | {v['energy']:>12.2f} | "
                      f"{v['peak']:>9.2f} | {v['clipping']:>12.2f}")
            print(f"TOPLAM: {total:.2f} kWh ({len(values)} saat)\n")

    print("BITTI: 3 sahanin gecmise donuk uretimi hesaplandi. "
          "Veritabanina yazilmadi; API istegi gonderilmedi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="3 saha icin tarihsel hava verisinden uretim hesabi")
    parser.add_argument("--db", default="solar.db", help="SQLite veritabani dosyasi")
    parser.add_argument("--start", default="2026-10-10", help="Baslangic tarihi YYYY-MM-DD")
    parser.add_argument("--end", default="2026-10-12", help="Bitis tarihi YYYY-MM-DD")
    parser.add_argument("--hourly", action="store_true", help="216 saatlik sonucun tumunu yazdir")
    args = parser.parse_args()
    run(args.db, args.start, args.end, hourly=args.hourly)
