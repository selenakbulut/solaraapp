
import sqlite3
from datetime import datetime, timezone

dc_power_kwp = 10
noct = 45
temperature_coefficient = -0.004
dc_loss = 0.05
ac_loss = 0.02
inverter_efficiency = 0.96
inverter_ac_power_kw = 8
panel_age_years = 5
annual_degradation = 0.005

age_factor = (1 - annual_degradation) ** panel_age_years

print("Panelin kalan güç oranı:", round(age_factor * 100, 2), "%")



def calculate_inverter_efficiency(dc_power_kw, inverter_power_kw):

    if dc_power_kw <= 0:
        return 0

    load_ratio = dc_power_kw / inverter_power_kw

    if load_ratio < 0.10:
        return 0.85
    elif load_ratio < 0.25:
        return 0.90
    elif load_ratio < 0.50:
        return 0.94
    elif load_ratio < 0.75:
        return 0.96
    else:
        return 0.97


connection = sqlite3.connect("solar.db")
cursor = connection.cursor()

cursor.execute("""
    SELECT
        forecast_time,
        temperature,
        tilted_radiation
    FROM weather_data
    WHERE site_id = 1
      AND tilt = 20
      AND azimuth = 0
    ORDER BY forecast_time
""")

weather_rows = cursor.fetchall()

print("Saat | Hava Sıcaklığı | Panel Sıcaklığı | Üretim (kWh)")
print("-" * 75)

saved_count = 0

for forecast_time, air_temp, radiation in weather_rows:

    if air_temp is None or radiation is None:
        continue

    #panel hücre sıcaklık
    cell_temp = air_temp + ((noct - 20) / 800) * radiation

    temp_factor = 1 + temperature_coefficient * (cell_temp - 25)

    energy_before_loss = (
        dc_power_kwp * (radiation / 1000) * temp_factor
    )

    dc_energy_kwh = (
            energy_before_loss
            * age_factor
            * (1 - dc_loss)
    )
    dc_power_kw = dc_energy_kwh / 1

    efficiency = calculate_inverter_efficiency(
        dc_power_kw,
        inverter_ac_power_kw
    )

    ac_energy_before_clipping = (
        dc_energy_kwh * efficiency
    )

    ac_energy_kwh = min(
        ac_energy_before_clipping,
        inverter_ac_power_kw * 1
    )

    final_energy_kwh = ac_energy_kwh * (1 - ac_loss)

    calculated_at = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        INSERT INTO production_forecasts (
            site_id,
            forecast_time,
            predicted_energy_kwh,
            tilt,
            azimuth,
            calculated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT(site_id, forecast_time, tilt, azimuth)
        DO UPDATE SET
            predicted_energy_kwh = excluded.predicted_energy_kwh,
            calculated_at = excluded.calculated_at
    """, (
        1,
        forecast_time,
        final_energy_kwh,
        20,
        0,
        calculated_at
    ))

    saved_count += cursor.rowcount


    print(
        forecast_time,
        "|",
        air_temp,
        "|",
        round(cell_temp, 2),
        "|",
        round(final_energy_kwh, 2)
    )

connection.commit()

print("Kaydedilen veya güncellenen tahmin sayısı:", saved_count)

connection.close()
