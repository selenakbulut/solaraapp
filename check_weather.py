
import sqlite3

connection = sqlite3.connect("solar.db")
cursor = connection.cursor()

site_id = 1
tilt = 20
azimuth = 0

start_time = "2026-10-13T00:00"
end_time = "2026-10-15T00:00"

cursor.execute("""
    SELECT COUNT(*)
    FROM weather_data
    WHERE site_id = ?
      AND tilt = ?
      AND azimuth = ?
      AND forecast_time >= ?
      AND forecast_time < ?
""", (
    site_id,
    tilt,
    azimuth,
    start_time,
    end_time
))

count = cursor.fetchone()[0]

print("Veritabanında bulunan saat sayısı:", count)

connection.close()
