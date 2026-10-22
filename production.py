
import sqlite3
from solar_model import calculate_total_loss
from datetime import datetime, timezone


def save_forecast(
    site_id,
    panel_count,
    panel_power_wp,
    ac_power_kw,
    site_age_years,
    tilt,
    azimuth,
    weather_df,
    site_losses = None,
    temperature_coefficient=-0.004
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
                       SELECT mounting_type
                       FROM sites
                       WHERE id = ?
                       """, (site_id,))

        site_row = cursor.fetchone()

        if site_row is None:
            raise ValueError("Santral bulunamadi.")

        mounting_type = site_row[0]

        loss_columns = [
            "soiling_loss",
            "reflection_loss",
            "mismatch_loss",
            "dc_cable_loss",
            "ac_cable_loss",
            "transformer_loss",
            "shading_loss",
            "availability_loss",
            "snow_loss"
        ]

        loss_values = [
            site_losses[column] if site_losses is not None else None
            for column in loss_columns
        ]

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
                            azimuth,
                            soiling_loss,
                            reflection_loss,
                            mismatch_loss,
                            dc_cable_loss,
                            ac_cable_loss,
                            transformer_loss,
                            shading_loss,
                            availability_loss,
                            snow_loss,
                            mounting_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                               ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           site_id,
                           created_at,
                           "v1.0",
                           panel_count,
                           panel_power_wp,
                           ac_power_kw,
                           site_age_years,
                           tilt,
                           azimuth,
                           *loss_values,
                           mounting_type
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

        if site_losses is None:
            effective_dc_loss = 0.05
            effective_ac_loss = 0.02

            explanation = (
                "Sahaya ozel kayip katsayilari bulunmadigi icin "
                "varsayilan DC %5 ve AC %2 kullanildi."
            )

        else:
            effective_dc_loss = calculate_total_loss([
                site_losses["soiling_loss"],
                site_losses["reflection_loss"],
                site_losses["mismatch_loss"],
                site_losses["dc_cable_loss"],
                site_losses["shading_loss"],
                site_losses["snow_loss"]
            ])

            effective_ac_loss = calculate_total_loss([
                site_losses["ac_cable_loss"],
                site_losses["transformer_loss"]
            ])

            explanation = (
                "Sahaya ozel dokuz kayip katsayisi kullanildi. "
                "Kullanilabilirlik kaybi ayrica uygulanir."
            )

        cursor.execute("""
            INSERT INTO forecast_assumptions (
                run_id,
                dc_loss,
                ac_loss,
                temperature_coefficient,
                annual_degradation,
                explanation
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            run_id,
            effective_dc_loss,
            effective_ac_loss,
            temperature_coefficient,
            0.005,
            explanation
        ))

        connection.commit()

        return run_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
