
import sqlite3

connection = sqlite3.connect("solar.db")
connection.execute("PRAGMA foreign_keys = ON")
cursor = connection.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    tilt REAL NOT NULL,
    azimuth REAL NOT NULL
)
""")

site_name = "Ankara GES"

cursor.execute(
    "SELECT * FROM sites WHERE name = ?",
    (site_name,)
)

existing_site = cursor.fetchone()

if existing_site is None:
    cursor.execute("""
        INSERT INTO sites (name, latitude, longitude, tilt, azimuth)
        VALUES (?, ?, ?, ?, ?)
    """, (site_name, 39.9334, 32.8597, 20, 0))

    print("Yeni santral eklendi.")
else:
    print("Bu santral zaten kayıtlı.")

cursor.execute("""
CREATE TABLE IF NOT EXISTS weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    forecast_time TEXT NOT NULL,
    temperature REAL,
    wind_speed REAL,
    cloud_cover REAL,
    shortwave_radiation REAL,
    tilted_radiation REAL,
    tilt REAL NOT NULL,
    azimuth REAL NOT NULL,
    fetched_at TEXT NOT NULL,

    FOREIGN KEY (site_id) REFERENCES sites(id),

    UNIQUE (site_id, forecast_time, tilt, azimuth)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS api_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_at TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status_code INTEGER,
    success INTEGER NOT NULL
)
""")

print("api_requests tablosu hazır.")


cursor.execute("""
CREATE TABLE IF NOT EXISTS production_forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,
    forecast_time TEXT NOT NULL,
    predicted_energy_kwh REAL NOT NULL,
    tilt REAL NOT NULL,
    azimuth REAL NOT NULL,
    calculated_at TEXT NOT NULL,

    FOREIGN KEY (site_id) REFERENCES sites(id),

    UNIQUE (site_id, forecast_time, tilt, azimuth)
)
""")

print("production_forecasts tablosu hazır.")


connection.commit()
connection.close()

print("Veritabanı hazır.")
