import sqlite3
from logger_config import logger

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

logger.info("sites tablosu hazır.")


cursor.execute("PRAGMA table_info(sites)")

existing_columns = [
    column[1] for column in cursor.fetchall()
]

new_columns = {
    "panel_count": "INTEGER",
    "panel_power_wp": "REAL",
    "ac_power_kw": "REAL",
    "site_age_years": "REAL",
    "elevation": "REAL",
    "timezone": "TEXT",
    "mounting_type": "TEXT"
}

for column_name, column_type in new_columns.items():

    if column_name not in existing_columns:

        cursor.execute(
            f"ALTER TABLE sites "
            f"ADD COLUMN {column_name} {column_type}"
        )

        logger.info("%s sütunu eklendi.", column_name)

    else:
        logger.info("%s zaten mevcut.", column_name)


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

logger.info("api_requests tablosu hazır.")


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

logger.info("forecast_runs tablosu hazır.")

cursor.execute("PRAGMA table_info(forecast_runs)")

run_columns = [
    column[1] for column in cursor.fetchall()
]

if "mounting_type" not in run_columns:
    cursor.execute("""
        ALTER TABLE forecast_runs
        ADD COLUMN mounting_type TEXT
    """)

    logger.info("forecast_runs tablosuna mounting_type eklendi.")

existing_columns = [
    column[1] for column in cursor.fetchall()
]

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

for column_name in loss_columns:

    if column_name not in run_columns:

        cursor.execute(
            f"ALTER TABLE forecast_runs "
            f"ADD COLUMN {column_name} REAL"
        )

        logger.info(
            "%s sütunu forecast_runs tablosuna eklendi.",
            column_name
        )


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

logger.info("forecast_results tablosu hazır.")

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

        logger.info("%s sütunu eklendi.", column_name)

    else:
        logger.info("%s zaten mevcut.", column_name)


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

logger.info("actual_production tablosu hazır.")


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

logger.info("site_losses tablosu hazır.")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS forecast_assumptions (
        run_id INTEGER PRIMARY KEY,
        dc_loss REAL NOT NULL,
        ac_loss REAL NOT NULL,
        temperature_coefficient REAL NOT NULL,
        annual_degradation REAL NOT NULL,
        explanation TEXT NOT NULL,

        FOREIGN KEY (run_id)
        REFERENCES forecast_runs(id)
    )
""")

logger.info("forecast_assumptions tablosu hazır.")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS geocoding_cache (
        query_name TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        elevation REAL,
        timezone TEXT,
        fetched_at TEXT NOT NULL
    )
""")

logger.info("geocoding_cache tablosu hazır.")

connection.commit()
connection.close()

logger.info("Veritabanı hazır.")

def get_site_losses(site_id):
    connection = sqlite3.connect("solar.db")

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                soiling_loss,
                reflection_loss,
                mismatch_loss,
                dc_cable_loss,
                ac_cable_loss,
                transformer_loss,
                shading_loss,
                availability_loss,
                snow_loss
            FROM site_losses
            WHERE site_id = ?
        """, (site_id,))

        row = cursor.fetchone()

        if row is None:
            return None

        columns = [
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

        return dict(zip(columns, row))

    finally:
        connection.close()

def save_site_losses(site_id, losses):

    columns = [
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

    if set(losses.keys()) != set(columns):
        raise ValueError("Dokuz kayıp katsayısının tamamı belirtilmelidir.")

    for name, value in losses.items():
        if not isinstance(value, (int, float)) or not 0 <= value < 1:
            raise ValueError(
                f"{name} için kayıp oranı 0 ile 1 arasında olmalıdır."
            )

    connection = sqlite3.connect("solar.db")
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        cursor = connection.cursor()

        cursor.execute("""
                       INSERT INTO site_losses (
                           site_id,
                           soiling_loss,
                           reflection_loss,
                           mismatch_loss,
                           dc_cable_loss,
                           ac_cable_loss,
                           transformer_loss,
                           shading_loss,
                           availability_loss,
                           snow_loss)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) 
                           ON CONFLICT(site_id)
                           DO UPDATE SET
                               soiling_loss = excluded.soiling_loss,
                               reflection_loss = excluded.reflection_loss,
                               mismatch_loss = excluded.mismatch_loss,
                               dc_cable_loss = excluded.dc_cable_loss,
                               ac_cable_loss = excluded.ac_cable_loss,
                               transformer_loss = excluded.transformer_loss,
                               shading_loss = excluded.shading_loss,
                               availability_loss = excluded.availability_loss,
                               snow_loss = excluded.snow_loss
                       """, (
                           site_id,
                           *[losses[column] for column in columns]
                       ))

        connection.commit()


    finally:
        connection.close()
