
from solar_model import calculate_production
from save_weather import save_weather_data

import sqlite3
import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Solar Production Forecast",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ Solar Production Forecast")
st.write("Ankara GES - Güneş Enerjisi Üretim Tahmini")


st.subheader("Santral Bilgileri")

with st.form("solar_form"):

    city = st.text_input(
        "Şehir",
        value="Ankara"
    )

    panel_count = st.number_input(
        "Panel Sayısı",
        min_value=1,
        value=20,
        step=1
    )

    panel_power_wp = st.number_input(
        "Bir Panelin Gücü (Wp)",
        min_value=1,
        value=500,
        step=50
    )

    inverter_power_kw = st.number_input(
        "İnverter AC Gücü (kW)",
        min_value=0.1,
        value=8.0,
        step=0.5
    )

    tilt = st.slider(
        "Panel Eğim Açısı (°)",
        min_value=0,
        max_value=90,
        value=20
    )

    azimuth = st.number_input(
        "Panel Azimutu (°)",
        min_value=-180,
        max_value=180,
        value=0
    )

    panel_age = st.number_input(
        "Santral Yaşı (Yıl)",
        min_value=0,
        value=5
    )

    submitted = st.form_submit_button(
        "Tahmin Oluştur"
    )


if submitted:

    dc_power_kwp = panel_count * panel_power_wp / 1000

    save_weather_data(tilt, azimuth)

    st.success("Santral bilgileri alındı!")

    st.write("Şehir:", city)
    st.write("DC Kurulu Güç:", dc_power_kwp, "kWp")
    st.write("İnverter Gücü:", inverter_power_kw, "kW")
    st.write("Eğim Açısı:", tilt, "°")
    st.write("Azimut:", azimuth, "°")
    st.write("Santral Yaşı:", panel_age, "yıl")

    connection = sqlite3.connect("solar.db")

    weather_query = """
        SELECT
            forecast_time,
            temperature,
            tilted_radiation
        FROM weather_data
        WHERE site_id = ?
          AND tilt = ?
          AND azimuth = ?
        ORDER BY forecast_time
    """

    weather_df = pd.read_sql_query(
        weather_query,
        connection,
        params=(1, tilt, azimuth)
    )

    connection.close()

    predictions = []

    for _, row in weather_df.iterrows():

        energy = calculate_production(
            radiation=row["tilted_radiation"],
            air_temp=row["temperature"],
            dc_power_kwp=dc_power_kwp,
            inverter_power_kw=inverter_power_kw,
            panel_age_years=panel_age
        )

        predictions.append(energy)

    weather_df["predicted_energy_kwh"] = predictions

    weather_df["forecast_time"] = pd.to_datetime(
        weather_df["forecast_time"]
    )

    weather_df["date"] = weather_df["forecast_time"].dt.date

    daily_df = (
        weather_df.groupby(
            "date",
            as_index=False
        )["predicted_energy_kwh"]
        .sum()
    )

    st.subheader("Genel Özet")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Toplam Tahmini Üretim",
            f"{weather_df['predicted_energy_kwh'].sum():.2f} kWh"
        )

    with col2:
        st.metric(
            "Tahmin Edilen Saat",
            len(weather_df)
        )

    st.subheader("Saatlik Üretim Tahmini")

    st.line_chart(
        weather_df.set_index(
            "forecast_time"
        )["predicted_energy_kwh"]
    )

    st.subheader("Günlük Üretim Tahmini")

    st.bar_chart(
        daily_df.set_index(
            "date"
        )["predicted_energy_kwh"]
    )

    st.subheader("Saatlik Veriler")

    st.dataframe(
        weather_df,
        use_container_width=True
    )

    csv_data = weather_df.to_csv(
        index=False
    ).encode("utf-8-sig")

    st.download_button(
        label="📥 Saatlik Tahminleri CSV Olarak İndir",
        data=csv_data,
        file_name="solar_production_forecast.csv",
        mime="text/csv"
    )


# gercek uretim verisi yukleme

st.subheader("Gerçek Üretim Verileri")

uploaded_file = st.file_uploader(
    "Gerçek üretim CSV dosyasını yükleyin",
    type=["csv"]
)

if uploaded_file is not None:

    actual_df = pd.read_csv(uploaded_file)

    st.write("Yüklenen gerçek üretim verileri:")

    st.dataframe(
        actual_df,
        use_container_width=True
    )

    st.success("CSV dosyası başarıyla okundu!")


    required_columns = [
        "production_time",
        "actual_energy_kwh"
    ]

    if not all(col in actual_df.columns for col in required_columns):
        st.error("CSV dosyasında gerekli sütunlar eksik!")

    else:
        actual_df["production_time"] = pd.to_datetime(
            actual_df["production_time"],
            errors="coerce"
        )

        actual_df["actual_energy_kwh"] = pd.to_numeric(
            actual_df["actual_energy_kwh"],
            errors="coerce"
        )

        invalid_rows = (
            actual_df["production_time"].isna()
            | actual_df["actual_energy_kwh"].isna()
            | (actual_df["actual_energy_kwh"] < 0)
        )

        if invalid_rows.any():
            st.error("CSV dosyasında geçersiz tarih veya üretim değeri var!")

        elif actual_df["production_time"].duplicated().any():
            st.error("CSV dosyasında aynı saat birden fazla kez bulunuyor!")

        else:
            if st.button("Gerçek Üretim Verilerini Kaydet"):

                connection = sqlite3.connect("solar.db")
                cursor = connection.cursor()

                for _, row in actual_df.iterrows():

                    production_time = row[
                        "production_time"
                    ].strftime("%Y-%m-%dT%H:%M")

                    actual_energy = float(
                        row["actual_energy_kwh"]
                    )

                    cursor.execute("""
                        INSERT INTO actual_production (
                            site_id,
                            production_time,
                            actual_energy_kwh
                        )
                        VALUES (?, ?, ?)

                        ON CONFLICT(site_id, production_time)
                        DO UPDATE SET
                            actual_energy_kwh = excluded.actual_energy_kwh
                    """, (
                        1,
                        production_time,
                        actual_energy
                    ))

                connection.commit()
                connection.close()

                st.success(
                    f"{len(actual_df)} gerçek üretim kaydı kaydedildi!"
                )

