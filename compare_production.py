
import sqlite3

connection = sqlite3.connect("solar.db")
cursor = connection.cursor()

cursor.execute("""
    SELECT
        p.forecast_time,
        p.predicted_energy_kwh,
        a.actual_energy_kwh
    FROM production_forecasts AS p
    INNER JOIN actual_production AS a
        ON p.site_id = a.site_id
        AND p.forecast_time = a.production_time
    WHERE p.site_id = 1
      AND p.tilt = 20
      AND p.azimuth = 0
    ORDER BY p.forecast_time
""")

rows = cursor.fetchall()

print("Saat | Tahmin (kWh) | Gerçek (kWh) | Mutlak Hata")
print("-" * 75)

for forecast_time, predicted, actual in rows:

    absolute_error = abs(predicted - actual)

    print(
        forecast_time,
        "|",
        round(predicted, 2),
        "|",
        round(actual, 2),
        "|",
        round(absolute_error, 2)
    )

print("Karşılaştırılan saat sayısı:", len(rows))

connection.close()
