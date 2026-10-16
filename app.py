from solar_model import calculate_production
from save_weather import save_weather_data
from production import save_forecast
from datetime import datetime
from io import BytesIO

import altair as alt
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Güneş Enerjisi Üretim Tahmini",
    page_icon="☀️",
    layout="wide"
)

st.title("☀️ Güneş Enerjisi Üretim Tahmini")
st.write("Güneş Enerjisi Üretim Tahmini")

connection = sqlite3.connect("solar.db")
cursor = connection.cursor()

cursor.execute("""
               SELECT COUNT(*)
               FROM api_requests
               WHERE date (requested_at) = ?
               """, (datetime.now().strftime("%Y-%m-%d"),))

daily_api_count = cursor.fetchone()[0]

connection.close()

st.metric("Bugünkü API İstek Sayısı", daily_api_count)

st.subheader("Santral Bilgileri")

connection = sqlite3.connect("solar.db")

site_df = pd.read_sql_query("""
                            SELECT id,
                                   name,
                                   panel_count,
                                   panel_power_wp,
                                   ac_power_kw,
                                   site_age_years,
                                   tilt,
                                   azimuth
                            FROM sites
                            ORDER BY name
                            """, connection)

connection.close()

selected_site_id = st.selectbox(
    "Tahmin Yapılacak Santrali Seçin",
    options=site_df["id"].tolist(),
    format_func=lambda site_id: (
        f"{site_df.loc[site_df['id'] == site_id, 'name'].iloc[0]} "
    )
)

site = site_df.loc[
    site_df["id"] == selected_site_id
    ].iloc[0]

if "site_success_message" in st.session_state:
    st.success(
        st.session_state.pop("site_success_message")
    )

with st.expander("➕ Yeni Santral Ekle"):
    with st.form("new_site_form"):
        new_site_name = st.text_input("Santral Adı")

        new_latitude = st.number_input(
            "Enlem (Latitude)",
            min_value=-90.0,
            max_value=90.0,
            value=39.9334,
            format="%.6f"
        )

        new_longitude = st.number_input(
            "Boylam (Longitude)",
            min_value=-180.0,
            max_value=180.0,
            value=32.8597,
            format="%.6f"
        )

        new_panel_count = st.number_input(
            "Panel Sayısı",
            min_value=1,
            value=20
        )

        new_panel_power = st.number_input(
            "Panel Gücü (Wp)",
            min_value=1,
            value=500
        )

        new_ac_power = st.number_input(
            "AC İnverter Gücü (kW)",
            min_value=0.1,
            value=8.0
        )

        new_tilt = st.slider(
            "Panel Eğimi (°)",
            min_value=0,
            max_value=90,
            value=20
        )

        new_azimuth = st.number_input(
            "Azimut (°)",
            min_value=-180,
            max_value=180,
            value=0
        )
        st.caption(
            "Panel yönü: 0° = Güney, "
            "-90° = Doğu, +90° = Batı, "
            "±180° = Kuzey"
        )

        new_site_age = st.number_input(
            "Santral Yaşı (Yıl)",
            min_value=0,
            value=0
        )

        new_site_submitted = st.form_submit_button(
            "Santrali Kaydet"
        )

if new_site_submitted:

    if not new_site_name.strip():
        st.error("Santral adı boş bırakılamaz.")

    else:
        new_dc_power_kwp = (
                new_panel_count * new_panel_power / 1000
        )

        new_dc_ac_ratio = new_dc_power_kwp / new_ac_power

        if new_dc_ac_ratio < 0.8 or new_dc_ac_ratio > 1.5:
            st.error(
                f"DC/AC güç oranı: {new_dc_ac_ratio:.2f}. "
                "Bu oran izin verilen 0.8–1.5 aralığının dışında. "
                "Santral kaydedilemez."
            )
            st.stop()

        connection = sqlite3.connect("solar.db")

        try:
            cursor = connection.cursor()

            cursor.execute("""
                           SELECT id
                           FROM sites
                           WHERE name = ?
                             AND latitude = ?
                             AND longitude = ?
                             AND panel_count = ?
                             AND panel_power_wp = ?
                             AND ac_power_kw = ?
                             AND tilt = ?
                             AND azimuth = ?
                             AND site_age_years = ?
                           """, (
                               new_site_name.strip(),
                               new_latitude,
                               new_longitude,
                               new_panel_count,
                               new_panel_power,
                               new_ac_power,
                               new_tilt,
                               new_azimuth,
                               new_site_age
                           ))

            existing_site = cursor.fetchone()

            if existing_site:
                st.warning(
                    "Bu santral aynı isim ve teknik bilgilerle zaten kayıtlı!"
                )
            else:
                cursor.execute("""
                               INSERT INTO sites (name, latitude, longitude,
                                                  panel_count, panel_power_wp,
                                                  ac_power_kw, tilt, azimuth, site_age_years)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                               """, (
                                   new_site_name.strip(),
                                   new_latitude,
                                   new_longitude,
                                   new_panel_count,
                                   new_panel_power,
                                   new_ac_power,
                                   new_tilt,
                                   new_azimuth,
                                   new_site_age
                               ))

                connection.commit()

                st.session_state["site_success_message"] = (
                    f"{new_site_name} santrali başarıyla kaydedildi!"
                )
                st.rerun()


        except sqlite3.Error as error:
            connection.rollback()
            st.error(f"Santral kaydedilemedi: {error}")

        finally:
            connection.close()

with st.form("solar_form"):
    city = st.text_input(
        "Santral",
        value=site["name"],
        disabled=True
    )

    panel_count = st.number_input(
        "Panel Sayısı",
        min_value=1,
        value=int(site["panel_count"])
    )

    panel_power_wp = st.number_input(
        "Panel Gücü (Wp)",
        min_value=1,
        value=int(site["panel_power_wp"])
    )

    inverter_power_kw = st.number_input(
        "İnverter Gücü (kW)",
        min_value=0.1,
        value=float(site["ac_power_kw"])
    )

    tilt = st.slider(
        "Panel Eğimi (°)",
        min_value=0,
        max_value=90,
        value=int(site["tilt"])
    )

    azimuth = st.number_input(
        "Azimut (°)",
        min_value=-180,
        max_value=180,
        value=int(site["azimuth"])
    )

    st.caption(
        "Panel yönü: 0° = Güney, "
        "-90° = Doğu, +90° = Batı, "
        "±180° = Kuzey"
    )

    panel_age = st.number_input(
        "Santral Yaşı (Yıl)",
        min_value=0,
        value=int(site["site_age_years"])
    )

    submitted = st.form_submit_button(
        "Tahmin Oluştur"
    )

if submitted:

    if not 0 <= tilt <= 90:
        st.error("Panel eğimi 0° ile 90° arasında olmalıdır.")
        st.stop()

    if panel_count <= 0:
        st.error("Panel sayısı 0'dan büyük olmalıdır.")
        st.stop()

    if panel_power_wp <= 0:
        st.error("Panel gücü 0'dan büyük olmalıdır.")
        st.stop()

    if inverter_power_kw <= 0:
        st.error("İnverter gücü 0'dan büyük olmalıdır.")
        st.stop()

    if not -180 <= azimuth <= 180:
        st.error("Azimut açısı -180° ile 180° arasında olmalıdır.")
        st.stop()

    if panel_age < 0:
        st.error("Santral yaşı negatif olamaz.")
        st.stop()

    dc_power_kwp = panel_count * panel_power_wp / 1000

    dc_ac_ratio = dc_power_kwp / inverter_power_kw

    st.write(f"DC/AC Güç Oranı: {dc_ac_ratio:.2f}")

    if dc_ac_ratio < 0.8 or dc_ac_ratio > 1.5:
        st.error(
            f"DC/AC güç oranı: {dc_ac_ratio:.2f}. "
            "Bu oran izin verilen 0.8–1.5 aralığının dışında. "
            "Tahmin oluşturulamaz."
        )
        st.stop()

    start_time, end_time = save_weather_data(
        int(selected_site_id),
        tilt,
        azimuth
    )

    st.success("Santral bilgileri alındı!")

    st.write("Şehir:", city)
    st.write("DC Kurulu Güç:", dc_power_kwp, "kWp")
    st.write("İnverter Gücü:", inverter_power_kw, "kW")
    st.write("Eğim Açısı:", tilt, "°")
    st.write("Azimut:", azimuth, "°")
    st.write("Santral Yaşı:", panel_age, "yıl")

    connection = sqlite3.connect("solar.db")

    weather_query = """
                    SELECT forecast_time, \
                           temperature, \
                           tilted_radiation
                    FROM weather_data
                    WHERE site_id = ?
                      AND tilt = ?
                      AND azimuth = ?
                      AND forecast_time >= ?
                      AND forecast_time < ?
                    ORDER BY forecast_time \
                    """

    weather_df = pd.read_sql_query(
        weather_query,
        connection,
        params=(int(selected_site_id),
                tilt,
                azimuth,
                start_time,
                end_time
                )
    )

    connection.close()

    predictions = []

    weather_df["cell_temperature"] = (
            weather_df["temperature"]
            + ((45 - 20) / 800) * weather_df["tilted_radiation"]
    )

    clipping_losses = []
    for _, row in weather_df.iterrows():
        energy, clipping = calculate_production(
            radiation=row["tilted_radiation"],
            air_temp=row["temperature"],
            dc_power_kwp=dc_power_kwp,
            inverter_power_kw=inverter_power_kw,
            panel_age_years=panel_age
        )

        predictions.append(energy)
        clipping_losses.append(clipping)

    weather_df["predicted_energy_kwh"] = predictions
    weather_df["average_power_kw"] = (
            weather_df["predicted_energy_kwh"] / 1.0
    )
    weather_df["clipping_loss_kwh"] = clipping_losses

    st.subheader("Saatlik İnverter Kırpma Kaybı")

    st.dataframe(
        weather_df[
            ["forecast_time", "predicted_energy_kwh", "clipping_loss_kwh"]
        ].rename(columns={
            "forecast_time": "Tarih / Saat",
            "predicted_energy_kwh": "Tahmini Üretim (kWh)",
            "clipping_loss_kwh": "Kırpma Kaybı (kWh)"
        }),
        hide_index=True
    )

    st.subheader("Saatlik Panel Hücre Sıcaklığı")

    st.dataframe(
        weather_df[
            ["forecast_time", "temperature", "cell_temperature"]
        ].rename(columns={
            "forecast_time": "Tarih / Saat",
            "temperature": "Hava Sıcaklığı (°C)",
            "cell_temperature": "Panel Hücre Sıcaklığı (°C)"
        }),
        hide_index=True
    )

    run_id = save_forecast(
        site_id=int(selected_site_id),
        panel_count=panel_count,
        panel_power_wp=panel_power_wp,
        ac_power_kw=inverter_power_kw,
        site_age_years=panel_age,
        tilt=tilt,
        azimuth=azimuth,
        weather_df=weather_df
    )

    st.success(
        f"Tahminler veritabanına kaydedildi! "
        f"Çalıştırma ID: {run_id}"
    )

    weather_df["forecast_time"] = pd.to_datetime(
        weather_df["forecast_time"]
    )
    weather_df["date"] = weather_df["forecast_time"].dt.date

    daily_clipping = (
        weather_df.groupby("date")["clipping_loss_kwh"]
        .sum()
        .reset_index()
    )

    st.subheader("Günlük Toplam İnverter Kırpma Kaybı")

    st.dataframe(
        daily_clipping.rename(columns={
            "date": "Tarih",
            "clipping_loss_kwh": "Toplam Kırpma Kaybı (kWh)"
        }),
        hide_index=True
    )

    daily_df = weather_df.groupby(
        "date", as_index=False
    ).agg(
        predicted_energy_kwh=("predicted_energy_kwh", "sum"),
        peak_power_kw=("predicted_energy_kwh", "max"),
        hour_count=("predicted_energy_kwh", "count")
    )

    daily_df["day_status"] = daily_df["hour_count"].apply(
        lambda hours: "Tam Gün" if hours == 24 else "Kısmi Gün"
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

    total_energy = weather_df["predicted_energy_kwh"].sum()

    st.metric(
        label="72 Saatlik Toplam Tahmini Üretim",
        value=f"{total_energy:.2f} kWh"
    )

    st.subheader("Saatlik Üretim Tahmini")

    st.markdown(
        """
        <span style="color:#2196F3;">●</span>
        **Tahmini Üretim (kWh)**
        &nbsp;&nbsp;&nbsp;&nbsp;
        <span style="color:#FF9800;">●</span>
        **Eğik Yüzey Işınımı (W/m²)**
        """,
        unsafe_allow_html=True
    )

    hourly_chart_df = weather_df.copy()

    hourly_chart_df["forecast_time"] = pd.to_datetime(
        hourly_chart_df["forecast_time"]
    )

    hourly_chart_df["next_hour"] = (
            hourly_chart_df["forecast_time"]
            + pd.Timedelta(hours=1)
    )

    x_axis = alt.X(
        "forecast_time:T",
        title="Tarih ve Saat",
        axis=alt.Axis(
            format="%d.%m %H:%M",
            labelAngle=-45
        )
    )

    hourly_chart = alt.Chart(hourly_chart_df).mark_line(
        color="#2196F3",
        strokeWidth=3
    ).encode(
        x=x_axis,
        y=alt.Y(
            "predicted_energy_kwh:Q",
            title="Tahmini Üretim (kWh)",
            axis=alt.Axis(
                titleColor="#2196F3",
                titleFontSize=14,
                titlePadding=15
            )
        )
    )

    radiation_chart = alt.Chart(hourly_chart_df).mark_line(
        color="#FF9800",
        strokeWidth=3
    ).encode(
        x=x_axis,
        y=alt.Y(
            "tilted_radiation:Q",
            title="Eğik Yüzey Işınımı (W/m²)",
            axis=alt.Axis(
                orient="right",
                titleColor="#FF9800",
                titleFontSize=14,
                titlePadding=15
            )
        )
    )

    hover_chart = alt.Chart(hourly_chart_df).mark_rect(
        opacity=0.001
    ).encode(
        x="forecast_time:T",
        x2="next_hour:T",
        y=alt.value(0),
        y2=alt.value(350),
        tooltip=[
            alt.Tooltip(
                "forecast_time:T",
                title="Tarih ve Saat",
                format="%d.%m.%Y %H:%M"
            ),
            alt.Tooltip(
                "predicted_energy_kwh:Q",
                title="Tahmini Üretim (kWh)",
                format=".3f"
            ),
            alt.Tooltip(
                "tilted_radiation:Q",
                title="Eğik Yüzey Işınımı (W/m²)",
                format=".2f"
            )
        ]
    )

    combined_chart = alt.layer(
        hourly_chart,
        radiation_chart,
        hover_chart
    ).resolve_scale(
        y="independent"
    ).properties(
        height=350
    )

    st.altair_chart(
        combined_chart,
        width="stretch"
    )

    partial_days = daily_df[
        daily_df["hour_count"] < 24
        ]

    if not partial_days.empty:
        st.info(
            "Not: Tahmin aralığının ilk ve son günü "
            "24 saatten az veri içerebilir. "
            "Bu günlerde gösterilen üretim miktarı "
            "yalnızca tahmin edilen saatlerin toplamıdır."
        )

    st.subheader("Günlük Üretim Tahmini")

    st.bar_chart(
        daily_df.set_index(
            "date"
        )["predicted_energy_kwh"]
    )

    st.subheader("Günlük Üretim Detayları")

    st.dataframe(
        daily_df.rename(columns={
            "date": "Tarih",
            "predicted_energy_kwh": "Tahmini Üretim (kWh)",
            "peak_power_kw": "Günlük Tepe Güç (kW)",
            "hour_count": "Saat Sayısı",
            "day_status": "Gün Durumu"
        }),
        width="stretch",
        hide_index=True
    )

    st.subheader("Saatlik Veriler")

    hourly_display_df = weather_df.rename(columns={
        "forecast_time": "Tarih / Saat",
        "temperature": "Hava Sıcaklığı (°C)",
        "tilted_radiation": "Eğik Yüzey Işınımı (W/m²)",
        "cell_temperature": "Panel Hücre Sıcaklığı (°C)",
        "predicted_energy_kwh": "Tahmini Üretim (kWh)",
        "average_power_kw": "Ortalama Güç (kW)",
        "clipping_loss_kwh": "İnverter Kırpma Kaybı (kWh)",
        "date": "Tarih"
    })

    st.dataframe(
        hourly_display_df,
        width="stretch",
        hide_index=True
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

    excel_buffer = BytesIO()

    daily_excel_df = daily_df.rename(columns={
        "date": "Tarih",
        "predicted_energy_kwh": "Tahmini Üretim (kWh)",
        "peak_power_kw": "Günlük Tepe Güç (kW)",
        "hour_count": "Saat Sayısı",
        "day_status": "Gün Durumu"
    })

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:

        hourly_display_df.to_excel(
            writer,
            sheet_name="Saatlik Tahminler",
            index=False
        )

        daily_excel_df.to_excel(
            writer,
            sheet_name="Günlük Özet",
            index=False
        )

        for sheet in writer.book.worksheets:

            for column in sheet.columns:
                column_letter = column[0].column_letter

                max_length = max(
                    len(str(cell.value))
                    if cell.value is not None else 0
                    for cell in column
                )

                sheet.column_dimensions[column_letter].width = min(
                    max(max_length + 3, 16),
                    42
                )

    st.download_button(
        label="📊 Tahminleri Excel Olarak İndir",
        data=excel_buffer.getvalue(),
        file_name="solar_production_forecast.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

st.subheader("Üretim Senaryo Karşılaştırması")

connection = sqlite3.connect("solar.db")

scenario_runs_df = pd.read_sql_query("""
                                     SELECT r.id        AS run_id,
                                            r.tilt,
                                            r.azimuth,
                                            r.created_at,
                                            r.panel_count,
                                            r.panel_power_wp,
                                            r.ac_power_kw,
                                            r.site_age_years,
                                            COUNT(f.id) AS hour_count
                                     FROM forecast_runs AS r
                                              INNER JOIN forecast_results AS f
                                                         ON r.id = f.run_id
                                     WHERE r.site_id = ?
                                     GROUP BY r.id
                                     ORDER BY r.id DESC
                                     """, connection, params=(int(selected_site_id),))

connection.close()

st.dataframe(
    scenario_runs_df.rename(columns={
        "run_id": "Tahmin ID",
        "tilt": "Panel Eğimi (°)",
        "azimuth": "Azimut (°)",
        "created_at": "Oluşturulma Zamanı",
        "panel_count": "Panel Sayısı",
        "panel_power_wp": "Panel Gücü (Wp)",
        "ac_power_kw": "İnverter Gücü (kW)",
        "site_age_years": "Santral Yaşı",
        "hour_count": "Saat Sayısı"
    }),
    width="stretch",
    hide_index=True
)

if len(scenario_runs_df) >= 2:

    scenario_labels = {
        int(row["run_id"]): (
            f"Tahmin {int(row['run_id'])} | "
            f"Eğim: {row['tilt']:g}°"
        )
        for _, row in scenario_runs_df.iterrows()
    }

    col1, col2 = st.columns(2)

    with col1:
        scenario_1 = st.selectbox(
            "Birinci Senaryo",
            options=scenario_runs_df["run_id"].tolist(),
            format_func=lambda run_id: scenario_labels[run_id]
        )

    with col2:
        scenario_2 = st.selectbox(
            "İkinci Senaryo",
            options=scenario_runs_df["run_id"].tolist(),
            index=1,
            format_func=lambda run_id: scenario_labels[run_id]
        )

    if scenario_1 == scenario_2:
        st.warning("Karşılaştırmak için iki farklı tahmin seçmelisiniz.")

    else:
        run_1 = scenario_runs_df.loc[
            scenario_runs_df["run_id"] == scenario_1
            ].iloc[0]

        run_2 = scenario_runs_df.loc[
            scenario_runs_df["run_id"] == scenario_2
            ].iloc[0]

        technical_columns = {
            "panel_count": "Panel Sayısı",
            "panel_power_wp": "Panel Gücü",
            "ac_power_kw": "İnverter Gücü",
            "site_age_years": "Santral Yaşı",
            "tilt": "Panel Eğimi",
            "azimuth": "Panel Yönü"
        }

        changed_parameters = [
            name
            for column, name in technical_columns.items()
            if run_1[column] != run_2[column]
        ]

        if len(changed_parameters) == 0:
            st.warning(
                "İki senaryonun teknik özellikleri aynı. "
                "En az bir parametre farklı olmalıdır."
            )

        elif len(changed_parameters) > 1:
            st.warning(
                "Birden fazla parametre farklı: "
                + ", ".join(changed_parameters)
                + ". Üretim farkının hangi parametreden "
                  "kaynaklandığını belirlemek zorlaşır."
            )

        else:
            st.success(
                f"Karşılaştırılan parametre: "
                f"{changed_parameters[0]}"
            )

        connection = sqlite3.connect("solar.db")

        scenario_comparison_df = pd.read_sql_query("""

                                                   SELECT a.forecast_time,
                                                          a.predicted_energy_kwh AS scenario_1_kwh,
                                                          b.predicted_energy_kwh AS scenario_2_kwh
                                                   FROM forecast_results AS a
                                                            INNER JOIN forecast_results AS b
                                                                       ON a.forecast_time = b.forecast_time
                                                   WHERE a.run_id = ?
                                                     AND b.run_id = ?
                                                   ORDER BY a.forecast_time
                                                   """, connection, params=(
            int(scenario_1),
            int(scenario_2)
        ))

        connection.close()

        if scenario_comparison_df.empty:
            st.warning(
                "Seçilen senaryoların ortak tahmin saati bulunmuyor."
            )
        else:
            st.write(
                f"Ortak tahmin saati sayısı: "
                f"{len(scenario_comparison_df)}"
            )

            scenario_comparison_df["difference_kwh"] = (
                    scenario_comparison_df["scenario_2_kwh"]
                    - scenario_comparison_df["scenario_1_kwh"]
            )

            total_1 = scenario_comparison_df["scenario_1_kwh"].sum()
            total_2 = scenario_comparison_df["scenario_2_kwh"].sum()

            energy_difference = total_2 - total_1

            if total_1 > 0:
                percentage_difference = (
                                                energy_difference / total_1
                                        ) * 100
            else:
                percentage_difference = None

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Senaryo 1 Üretimi",
                    f"{total_1:.2f} kWh"
                )

            with col2:
                st.metric(
                    "Senaryo 2 Üretimi",
                    f"{total_2:.2f} kWh"
                )

            with col3:
                st.metric(
                    "Üretim Farkı",
                    f"{energy_difference:+.2f} kWh",
                    delta=(
                        f"{percentage_difference:+.2f}%"
                        if percentage_difference is not None
                        else None
                    )
                )

            st.subheader("Saatlik Senaryo Karşılaştırması")

            hourly_scenario_display = scenario_comparison_df.rename(
                columns={
                    "forecast_time": "Tarih / Saat",
                    "scenario_1_kwh": "Senaryo 1 Üretimi (kWh)",
                    "scenario_2_kwh": "Senaryo 2 Üretimi (kWh)",
                    "difference_kwh": "Üretim Farkı (kWh)"
                }
            )

            st.dataframe(
                hourly_scenario_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Senaryo 1 Üretimi (kWh)": st.column_config.NumberColumn(
                        format="%.3f"
                    ),
                    "Senaryo 2 Üretimi (kWh)": st.column_config.NumberColumn(
                        format="%.3f"
                    ),
                    "Üretim Farkı (kWh)": st.column_config.NumberColumn(
                        format="%+.3f"
                    )
                }
            )

else:
    st.info("Karşılaştırma için en az iki tahmin gereklidir.")

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
        width="stretch"
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
                                   INSERT INTO actual_production (site_id,
                                                                  production_time,
                                                                  actual_energy_kwh)
                                   VALUES (?, ?, ?) ON CONFLICT(site_id, production_time)
                        DO
                                   UPDATE SET
                                       actual_energy_kwh = excluded.actual_energy_kwh
                                   """, (
                                       int(selected_site_id),
                                       production_time,
                                       actual_energy
                                   ))

                connection.commit()
                connection.close()

                st.success(
                    f"{len(actual_df)} gerçek üretim kaydı kaydedildi!"
                )

st.subheader("Tahmin ve Gerçek Üretim Karşılaştırması")

connection = sqlite3.connect("solar.db")

runs_df = pd.read_sql_query("""
                            SELECT r.id,
                                   s.name               AS site_name,
                                   r.created_at,
                                   r.tilt,
                                   r.azimuth,
                                   MIN(f.forecast_time) AS start_time,
                                   MAX(f.forecast_time) AS end_time,
                                   COUNT(f.id)          AS hour_count
                            FROM forecast_runs AS r
                                     INNER JOIN sites AS s
                                                ON r.site_id = s.id
                                     INNER JOIN forecast_results AS f
                                                ON r.id = f.run_id
                            WHERE r.site_id = ?
                            GROUP BY r.id,
                                     s.name,
                                     r.created_at,
                                     r.tilt,
                                     r.azimuth
                            ORDER BY r.id DESC
                            """, connection, params=(int(selected_site_id),))

connection.close()

selected_run_id = None

if runs_df.empty:
    st.info("Henüz kaydedilmiş tahmin bulunmuyor.")
else:
    run_labels = {}

    for _, row in runs_df.iterrows():
        created_at = pd.to_datetime(
            row["created_at"],
            utc=True
        ).tz_convert("Europe/Istanbul")

        created_text = created_at.strftime(
            "%d.%m.%Y %H:%M"
        )

        run_labels[int(row["id"])] = (
            f"{row['site_name']} | "
            f"{created_text} | "
            f"Eğim: {row['tilt']:g}°"
        )

    selected_run_id = st.selectbox(
        "Karşılaştırılacak Tahmini Seçin",
        options=runs_df["id"].tolist(),
        format_func=lambda run_id: run_labels[run_id]
    )

connection = sqlite3.connect("solar.db")

comparison_query = """
                   SELECT f.forecast_time, \
                          f.predicted_energy_kwh, \
                          a.actual_energy_kwh
                   FROM forecast_results AS f
                            INNER JOIN forecast_runs AS r
                                       ON f.run_id = r.id
                            INNER JOIN actual_production AS a
                                       ON r.site_id = a.site_id
                                           AND f.forecast_time = a.production_time
                   WHERE f.run_id = ?
                   ORDER BY f.forecast_time \
                   """

comparison_df = pd.read_sql_query(
    comparison_query,
    connection,
    params=(selected_run_id,)
)

connection.close()

comparison_mode = st.radio(
    "Karşılaştırma Modu",
    options=[
        "Saatlik Karşılaştırma",
        "Günlük Karşılaştırma"
    ],
    horizontal=True
)

if comparison_df.empty:

    st.info("Karşılaştırılacak gerçek üretim verisi bulunamadı.")

else:

    comparison_df["forecast_time"] = pd.to_datetime(
        comparison_df["forecast_time"]
    )

    comparison_df["absolute_error"] = (
            comparison_df["predicted_energy_kwh"]
            - comparison_df["actual_energy_kwh"]
    ).abs()

    comparison_df["percentage_deviation"] = (
                                                    (
                                                            comparison_df["predicted_energy_kwh"]
                                                            - comparison_df["actual_energy_kwh"]
                                                    )
                                                    / comparison_df["actual_energy_kwh"].replace(0, float("nan"))
                                            ) * 100

    comparison_df["deviation_status"] = comparison_df[
        "percentage_deviation"
    ].apply(
        lambda value: (
            "Hesaplanamaz" if pd.isna(value)
            else "Yüksek Tahmin" if value > 0
            else "Düşük Tahmin" if value < 0
            else "Tam İsabet"
        )
    )

    mae = comparison_df["absolute_error"].mean()

    rmse = (
                   (
                           comparison_df["predicted_energy_kwh"]
                           - comparison_df["actual_energy_kwh"]
                   ) ** 2
           ).mean() ** 0.5

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Ortalama Mutlak Hata", f"{mae:.3f} kWh")

    with col2:
        st.metric("Ortalama Karekök Hata", f"{rmse:.3f} kWh")

    with col3:
        st.metric("Karşılaştırılan Saat", len(comparison_df))

    if comparison_mode == "Saatlik Karşılaştırma":
        st.subheader("Tahmin ve Gerçek Üretim Grafiği")

        chart_df = comparison_df.set_index("forecast_time")[
            ["predicted_energy_kwh", "actual_energy_kwh"]
        ].copy()

        chart_df = chart_df.rename(columns={
            "predicted_energy_kwh": "Tahmin Edilen Üretim (kWh)",
            "actual_energy_kwh": "Gerçek Üretim (kWh)"
        })

        hourly_comparison_df = chart_df.reset_index()

        hourly_comparison_df = hourly_comparison_df.melt(
            id_vars="forecast_time",
            var_name="Üretim Türü",
            value_name="Enerji (kWh)"
        )

        lines = alt.Chart(hourly_comparison_df).mark_line().encode(
            x=alt.X(
                "forecast_time:T",
                title="Tarih ve Saat",
                axis=alt.Axis(
                    format="%d.%m %H:%M",
                    labelAngle=-45
                )
            ),
            y=alt.Y(
                "Enerji (kWh):Q",
                title="Enerji (kWh)"
            ),
            color=alt.Color(
                "Üretim Türü:N",
                scale=alt.Scale(
                    domain=[
                        "Tahmin Edilen Üretim (kWh)",
                        "Gerçek Üretim (kWh)"
                    ],
                    range=["#2196F3", "#4CAF50"]
                ),
                title="Üretim Türü"
            )
        )

        nearest = alt.selection_point(
            nearest=True,
            on="pointerover",
            fields=["forecast_time"],
            empty=False
        )

        selectors = alt.Chart(hourly_comparison_df).mark_point(
            opacity=0
        ).encode(
            x="forecast_time:T"
        ).add_params(nearest)

        points = lines.mark_point(size=65).encode(
            opacity=alt.condition(
                nearest,
                alt.value(1),
                alt.value(0)
            )
        )

        tooltips = lines.mark_point(
            opacity=0,
            size=100
        ).encode(
            tooltip=[
                alt.Tooltip(
                    "forecast_time:T",
                    title="Tarih ve Saat",
                    format="%d.%m.%Y %H:%M"
                ),
                alt.Tooltip(
                    "Üretim Türü:N",
                    title="Üretim Türü"
                ),
                alt.Tooltip(
                    "Enerji (kWh):Q",
                    title="Üretim (kWh)",
                    format=".3f"
                )
            ]
        )

        hourly_comparison_chart = alt.layer(
            lines,
            selectors,
            points,
            tooltips
        ).properties(
            height=350
        )

        st.altair_chart(
            hourly_comparison_chart,
            width="stretch"
        )

        st.subheader("Karşılaştırma Tablosu")

        display_df = comparison_df.rename(columns={
            "forecast_time": "Tarih ve Saat",
            "predicted_energy_kwh": "Tahmin Edilen Üretim (kWh)",
            "actual_energy_kwh": "Gerçek Üretim (kWh)",
            "absolute_error": "Mutlak Hata (kWh)",
            "percentage_deviation": "Yüzde Sapma (%)",
            "deviation_status": "Tahmin Durumu"
        })

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Tahmin Edilen Üretim (kWh)": st.column_config.NumberColumn(
                    format="%.3f"
                ),
                "Gerçek Üretim (kWh)": st.column_config.NumberColumn(
                    format="%.3f"
                ),
                "Mutlak Hata (kWh)": st.column_config.NumberColumn(
                    format="%.3f"
                ),
                "Yüzde Sapma (%)": st.column_config.NumberColumn(
                    format="%+.2f"
                )

            }
        )

    if comparison_mode == "Günlük Karşılaştırma":
        st.subheader("Günlük Üretim Karşılaştırması")

        comparison_df["date"] = (
            comparison_df["forecast_time"].dt.date
        )

        daily_comparison = comparison_df.groupby("date")[
            ["predicted_energy_kwh", "actual_energy_kwh"]
        ].sum().reset_index()

        daily_comparison = daily_comparison.rename(columns={
            "date": "Tarih",
            "predicted_energy_kwh": "Tahmin Edilen Üretim (kWh)",
            "actual_energy_kwh": "Gerçek Üretim (kWh)"
        })

        st.dataframe(
            daily_comparison,
            width="stretch",
            hide_index=True
        )

        st.subheader("Günlük Tahmin ve Gerçek Üretim Grafiği")

        daily_chart_df = daily_comparison.copy()

        daily_chart_df["Tarih"] = pd.to_datetime(
            daily_chart_df["Tarih"]
        ).dt.strftime("%d.%m.%Y")

        daily_chart_df = daily_chart_df.rename(columns={
            "Tahmin Edilen Üretim (kWh)": "Tahmin",
            "Gerçek Üretim (kWh)": "Gerçek"
        })

        chart_data = daily_chart_df.melt(
            id_vars="Tarih",
            value_vars=["Tahmin", "Gerçek"],
            var_name="Üretim Türü",
            value_name="Enerji (kWh)"
        )

        daily_chart = alt.Chart(chart_data).mark_bar(
            size=65
        ).encode(
            x=alt.X(
                "Üretim Türü:N",
                title=None,
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y(
                "Enerji (kWh):Q",
                title="Enerji (kWh)",
                scale=alt.Scale(zero=True)
            ),
            color=alt.Color(
                "Üretim Türü:N",
                scale=alt.Scale(
                    domain=["Tahmin", "Gerçek"],
                    range=["#2196F3", "#4CAF50"]
                ),
                title="Üretim Türü"
            ),
            column=alt.Column(
                "Tarih:N",
                title=None,
                header=alt.Header(labelOrient="bottom")
            ),
            tooltip=[
                "Tarih",
                "Üretim Türü",
                alt.Tooltip("Enerji (kWh):Q", format=".3f")
            ]
        ).properties(
            width=250,
            height=320
        )

        st.altair_chart(daily_chart)

        st.subheader("Günlük Üretim Hatası")

        st.info(
            "Günlük karşılaştırmalar yalnızca tahmin ve gerçek üretim "
            "verilerinin eşleştiği saatler üzerinden hesaplanır. "
            "24 saatten az eşleşme bulunan günler 'Eksik Veri' olarak "
            "işaretlenir. Bu günlerdeki toplamlar tam günlük üretimi göstermez."
        )

        daily_comparison["Yüzde Sapma (%)"] = (
                                                      (
                                                              daily_comparison["Tahmin Edilen Üretim (kWh)"]
                                                              - daily_comparison["Gerçek Üretim (kWh)"]
                                                      )
                                                      / daily_comparison["Gerçek Üretim (kWh)"].replace(
                                                  0, float("nan")
                                              )
                                              ) * 100

        daily_comparison["Mutlak Hata (kWh)"] = (
                daily_comparison["Tahmin Edilen Üretim (kWh)"]
                - daily_comparison["Gerçek Üretim (kWh)"]
        ).abs()

        hour_counts = comparison_df.groupby("date").size()

        daily_comparison["Karşılaştırılan Saat Sayısı"] = (
            pd.to_datetime(daily_comparison["Tarih"])
            .dt.date
            .map(hour_counts)
        )

        daily_comparison["Veri Durumu"] = (
            daily_comparison["Karşılaştırılan Saat Sayısı"]
            .apply(lambda count: "Tam Gün" if count == 24 else "Eksik Veri")
        )

        st.dataframe(
            daily_comparison,
            width="stretch",
            hide_index=True,
            column_config={
                "Yüzde Sapma (%)": st.column_config.NumberColumn(
                    format="%+.2f"
                ),
                "Mutlak Hata (kWh)": st.column_config.NumberColumn(
                    format="%.3f"
                )
            }
        )



