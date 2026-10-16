
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
        azimuth REAL NOT NULL,
        panel_count INTEGER,
        panel_power_wp REAL,
        ac_power_kw REAL,
        site_age_years REAL
    )
""")

print("sites tablosu hazır.")


cursor.execute("PRAGMA table_info(sites)")

existing_columns = [
    column[1] for column in cursor.fetchall()
]

new_columns = {
    "panel_count": "INTEGER",
    "panel_power_wp": "REAL",
    "ac_power_kw": "REAL",
    "site_age_years": "REAL"
}

for column_name, column_type in new_columns.items():

    if column_name not in existing_columns:

        cursor.execute(
            f"ALTER TABLE sites "
            f"ADD COLUMN {column_name} {column_type}"
        )

        print(column_name, "sütunu eklendi.")

    else:
        print(column_name, "zaten mevcut.")


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
    UPDATE sites
    SET
        panel_count = ?,
        panel_power_wp = ?,
        ac_power_kw = ?,
        site_age_years = ?
    WHERE name = ?
      AND panel_count IS NULL
      AND panel_power_wp IS NULL
      AND ac_power_kw IS NULL
      AND site_age_years IS NULL
""", (
    20,
    500,
    8,
    5,
    "Ankara GES"
))

print("Ankara GES teknik bilgileri kontrol edildi.")


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


cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        model_version TEXT NOT NULL,
        panel_count INTEGER NOT NULL,
        panel_power_wp REAL NOT NULL,
        ac_power_kw REAL NOT NULL,
        site_age_years REAL NOT NULL,
        tilt REAL NOT NULL,
        azimuth REAL NOT NULL,

        FOREIGN KEY (site_id) REFERENCES sites(id)
    )
""")

print("forecast_runs tablosu hazır.")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        forecast_time TEXT NOT NULL,
        predicted_energy_kwh REAL NOT NULL,

        FOREIGN KEY (run_id) REFERENCES forecast_runs(id),

        UNIQUE (run_id, forecast_time)
    )
""")

print("forecast_results tablosu hazır.")

cursor.execute("PRAGMA table_info(forecast_results)")

existing_columns = [
    column[1] for column in cursor.fetchall()
]

new_columns = {
    "cell_temperature": "REAL",
    "clipping_loss_kwh": "REAL"
}

for column_name, column_type in new_columns.items():

    if column_name not in existing_columns:

        cursor.execute(
            f"ALTER TABLE forecast_results "
            f"ADD COLUMN {column_name} {column_type}"
        )

        print(column_name, "sütunu eklendi.")

    else:
        print(column_name, "zaten mevcut.")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS actual_production (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL,
        production_time TEXT NOT NULL,
        actual_energy_kwh REAL NOT NULL,
        FOREIGN KEY (site_id) REFERENCES sites(id),
        UNIQUE(site_id, production_time)
    )
""")

print("actual_production tablosu hazır.")


cursor.execute("""
    CREATE TABLE IF NOT EXISTS site_losses (
        site_id INTEGER PRIMARY KEY,
        soiling_loss REAL NOT NULL DEFAULT 0,
        reflection_loss REAL NOT NULL DEFAULT 0,
        mismatch_loss REAL NOT NULL DEFAULT 0,
        dc_cable_loss REAL NOT NULL DEFAULT 0,
        ac_cable_loss REAL NOT NULL DEFAULT 0,
        transformer_loss REAL NOT NULL DEFAULT 0,
        shading_loss REAL NOT NULL DEFAULT 0,
        availability_loss REAL NOT NULL DEFAULT 0,
        snow_loss REAL NOT NULL DEFAULT 0,

        FOREIGN KEY (site_id) REFERENCES sites(id)
    )
""")

print("site_losses tablosu hazır.")

connection.commit()
connection.close()

print("Veritabanı hazır.")
