
import sqlite3

connection = sqlite3.connect("solar.db")
cursor = connection.cursor()

cursor.execute("""
    SELECT
        DATE(forecast_time) AS forecast_date,
        COUNT(*) AS hour_count,
        SUM(predicted_energy_kwh) AS total_energy
    FROM production_forecasts
    WHERE site_id = 1
      AND tilt = 20
      AND azimuth = 0
    GROUP BY DATE(forecast_time)
    ORDER BY forecast_date
""")

daily_results = cursor.fetchall()

print("Tarih | Saat Sayısı | Günlük Üretim (kWh)")
print("-" * 55)

for forecast_date, hour_count, total_energy in daily_results:
    print(
        forecast_date,
        "|",
        hour_count,
        "|",
        round(total_energy, 2)
    )

connection.close()
