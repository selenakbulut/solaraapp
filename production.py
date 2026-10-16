
import sqlite3
from datetime import datetime, timezone


def save_forecast(
    site_id,
    panel_count,
    panel_power_wp,
    ac_power_kw,
    site_age_years,
    tilt,
    azimuth,
    weather_df
):

    created_at = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )

    if weather_df.empty:
        raise ValueError("Kaydedilecek tahmin verisi bulunamadı.")

    if not {
        "forecast_time",
        "predicted_energy_kwh",
        "cell_temperature",
        "clipping_loss_kwh"
    }.issubset(weather_df.columns):
        raise ValueError("Tahmin verisinde gerekli sütunlar eksik.")

    connection = sqlite3.connect("solar.db")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO forecast_runs (
                site_id,
                created_at,
                model_version,
                panel_count,
                panel_power_wp,
                ac_power_kw,
                site_age_years,
                tilt,
                azimuth
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            site_id,
            created_at,
            "v1.0",
            panel_count,
            panel_power_wp,
            ac_power_kw,
            site_age_years,
            tilt,
            azimuth
        ))

        run_id = cursor.lastrowid

        forecast_rows = []

        for _, row in weather_df.iterrows():

            forecast_time = row["forecast_time"]

            if hasattr(forecast_time, "strftime"):
                forecast_time = forecast_time.strftime(
                    "%Y-%m-%dT%H:%M"
                )

            forecast_rows.append((
                run_id,
                forecast_time,
                float(row["predicted_energy_kwh"]),
                float(row["cell_temperature"]),
                float(row["clipping_loss_kwh"])
            ))

        cursor.executemany("""
            INSERT INTO forecast_results (
                run_id,
                forecast_time,
                predicted_energy_kwh,
                cell_temperature,
                clipping_loss_kwh
            )
            VALUES (?, ?, ?, ?, ?)
        """, forecast_rows)

        connection.commit()

        return run_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
