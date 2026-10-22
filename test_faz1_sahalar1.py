import sqlite3
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from solar_model import calculate_production, calculate_total_loss


SAHALAR = (
    ("Saha 1", 91327, 550, 39700, 2),
    ("Saha 2", 17854, 550, 7500, 3),
    ("Saha 3", 7123, 550, 3500, 1),
)


class TestFaz1Sahalar(unittest.TestCase):
    def test_uc_saha_dc_ac_oranlari(self):
        oranlar = {}
        for ad, panel_sayisi, panel_wp, inverter_kw, _yas in SAHALAR:
            with self.subTest(saha=ad):
                dc_kwp = panel_sayisi * panel_wp / 1000.0
                oran = dc_kwp / inverter_kw
                self.assertGreater(oran, 1.0)
                oranlar[ad] = oran
                print(f"{ad}: DC {dc_kwp:.2f} kWp | AC {inverter_kw:.2f} kW | DC/AC {oran:.4f}")

        self.assertEqual(len(set(oranlar.values())), 3, "Uc sahanin DC/AC oranlari farkli olmali")
        self.assertGreater(oranlar["Saha 2"], oranlar["Saha 1"])
        self.assertGreater(oranlar["Saha 1"], oranlar["Saha 3"])

    def test_uc_saha_gunduz_sinir(self):
        for ad, panel_sayisi, panel_wp, inverter_kw, yas in SAHALAR:
            with self.subTest(saha=ad):
                dc_kwp = panel_sayisi * panel_wp / 1000
                enerji, kirpma = calculate_production(
                    radiation=650,
                    air_temp=25,
                    dc_power_kwp=dc_kwp,
                    inverter_power_kw=inverter_kw,
                    panel_age_years=yas,
                )
                self.assertGreater(enerji, 0)
                self.assertLessEqual(enerji, inverter_kw)
                self.assertGreaterEqual(kirpma, 0)

    def test_uc_saha_gece_sifir_uretim(self):
        for ad, panel_sayisi, panel_wp, inverter_kw, yas in SAHALAR:
            with self.subTest(saha=ad):
                enerji, kirpma = calculate_production(
                    radiation=0,
                    air_temp=20,
                    dc_power_kwp=panel_sayisi * panel_wp / 1000,
                    inverter_power_kw=inverter_kw,
                    panel_age_years=yas,
                )
                self.assertEqual(enerji, 0)
                self.assertEqual(kirpma, 0)

    def test_uc_saha_sicaklik(self):
        for ad, panel_sayisi, panel_wp, inverter_kw, yas in SAHALAR:
            with self.subTest(saha=ad):
                params = dict(
                    radiation=650,
                    dc_power_kwp=panel_sayisi * panel_wp / 1000,
                    inverter_power_kw=inverter_kw,
                    panel_age_years=yas,
                )
                soguk, _ = calculate_production(air_temp=15, **params)
                sicak, _ = calculate_production(air_temp=40, **params)
                self.assertGreater(soguk, sicak)

    def test_uc_saha_yaslanma(self):
        for ad, panel_sayisi, panel_wp, inverter_kw, yas in SAHALAR:
            with self.subTest(saha=ad):
                params = dict(
                    radiation=650,
                    air_temp=25,
                    dc_power_kwp=panel_sayisi * panel_wp / 1000,
                    inverter_power_kw=inverter_kw,
                )
                yeni, _ = calculate_production(panel_age_years=0, **params)
                yasli, _ = calculate_production(panel_age_years=15, **params)
                self.assertGreater(yeni, yasli)

    def test_uc_saha_clipping(self):
        for ad, panel_sayisi, panel_wp, _inverter_kw, yas in SAHALAR:
            with self.subTest(saha=ad):
                dc_kwp = panel_sayisi * panel_wp / 1000
                dusuk_ac_kw = dc_kwp * 0.2
                enerji, kirpma = calculate_production(
                    radiation=1000,
                    air_temp=25,
                    dc_power_kwp=dc_kwp,
                    inverter_power_kw=dusuk_ac_kw,
                    panel_age_years=yas,
                )
                self.assertGreater(kirpma, 0)
                self.assertGreater(enerji, 0)
                self.assertLessEqual(enerji, dusuk_ac_kw)

    def test_uc_saha_yaslanma_sirala(self):
        kayiplar = {}
        for ad, panel_sayisi, panel_wp, _inverter_kw, yas in SAHALAR:
            with self.subTest(saha=ad):
                dc_kwp = panel_sayisi * panel_wp / 1000
                params = dict(
                    radiation=650,
                    air_temp=25,
                    dc_power_kwp=dc_kwp,
                    inverter_power_kw=dc_kwp,
                )
                yeni, _ = calculate_production(panel_age_years=0, **params)
                yasli, _ = calculate_production(panel_age_years=yas, **params)
                kayip_orani = 1 - yasli / yeni
                kayiplar[ad] = kayip_orani
                self.assertAlmostEqual(
                    kayip_orani,
                    1 - (1 - 0.005) ** yas,
                    places=7,
                )

        self.assertLess(kayiplar["Saha 3"], kayiplar["Saha 1"])
        self.assertLess(kayiplar["Saha 1"], kayiplar["Saha 2"])

    def test_uc_saha_guney_kuzey_uretim(self):
        db_file = Path(__file__).resolve().parent / "solar.db"
        if not db_file.is_file():
            self.skipTest("Yerel solar.db yok: tarihsel yon testi atlandi.")

        expected = [
            (datetime(2026, 10, 10) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
            for i in range(72)
        ]

        with closing(sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True)) as connection:
            has_table = connection.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'historical_weather_data'
            """).fetchone()
            if not has_table:
                self.skipTest("Tarihsel veri tablosu yok: yon testi atlandi.")

            for site_id, expected_name in ((12, "Saha 1"), (13, "Saha 2"), (14, "Saha 3")):
                with self.subTest(saha=expected_name):
                    site = connection.execute("""
                        SELECT name, latitude, longitude, tilt,
                               panel_count, panel_power_wp, ac_power_kw, site_age_years
                        FROM sites WHERE id = ?
                    """, (site_id,)).fetchone()
                    self.assertIsNotNone(site, f"{expected_name}: santral bulunamadi")
                    name, lat, lon, tilt, panels, wp, inverter_kw, age = site
                    self.assertEqual(name, expected_name)
                    self.assertTrue(all(value is not None for value in (panels, wp, inverter_kw, age)))

                    def read_weather(azimuth):
                        return connection.execute("""
                            SELECT weather_time, temperature, tilted_radiation
                            FROM historical_weather_data
                            WHERE site_id = ? AND latitude = ? AND longitude = ?
                              AND tilt = ? AND azimuth = ?
                              AND weather_time >= ? AND weather_time <= ?
                            ORDER BY weather_time
                        """, (site_id, lat, lon, tilt, azimuth, expected[0], expected[-1])).fetchall()

                    south = read_weather(0)
                    north = read_weather(180)
                    self.assertEqual([r[0] for r in south], expected,
                                     f"{name}: guney verisi 72 saat degil")
                    self.assertEqual([r[0] for r in north], expected,
                                     f"{name}: kuzey verisi 72 saat degil")

                    dc_kwp = panels * wp / 1000.0
                    south_total = north_total = 0.0
                    for (_, south_temp, south_radiation), (_, _, north_radiation) in zip(south, north):
                        params = dict(
                            air_temp=float(south_temp),
                            dc_power_kwp=dc_kwp,
                            inverter_power_kw=float(inverter_kw),
                            panel_age_years=float(age),
                        )
                        south_total += calculate_production(
                            radiation=float(south_radiation), **params
                        )[0]
                        north_total += calculate_production(
                            radiation=float(north_radiation), **params
                        )[0]

                    print(f"{name}: Guney {south_total:.2f} kWh | "
                          f"Kuzey {north_total:.2f} kWh (72 saat)")
                    self.assertGreater(south_total, north_total,
                                       f"{name}: guney toplam uretimi kuzeyden buyuk degil")

    def test_uc_saha_egim(self):
        db_file = Path(__file__).resolve().parent / "solar.db"
        if not db_file.is_file():
            self.skipTest("Yerel solar.db yok: tarihsel egim testi atlandi.")

        expected = [
            (datetime(2026, 10, 10) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
            for i in range(72)
        ]

        with closing(sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True)) as connection:
            has_table = connection.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type='table' AND name='historical_weather_data'
            """).fetchone()
            if not has_table:
                self.skipTest("Tarihsel veri tablosu yok: egim testi atlandi.")

            for site_id, expected_name in ((12, "Saha 1"), (13, "Saha 2"), (14, "Saha 3")):
                with self.subTest(saha=expected_name):
                    row = connection.execute("""
                        SELECT name, latitude, longitude, tilt,
                               panel_count, panel_power_wp, ac_power_kw, site_age_years
                        FROM sites WHERE id = ?
                    """, (site_id,)).fetchone()
                    self.assertIsNotNone(row, f"{expected_name}: santral bulunamadi")
                    name, lat, lon, original_tilt, panels, wp, ac_kw, years = row
                    self.assertEqual(name, expected_name)
                    self.assertTrue(all(x is not None for x in (panels, wp, ac_kw, years)))
                    self.assertNotIn(float(original_tilt), (0.0, 90.0))

                    def read_weather(tilt):
                        records = connection.execute("""
                            SELECT weather_time, temperature, tilted_radiation
                            FROM historical_weather_data
                            WHERE site_id = ? AND latitude = ? AND longitude = ?
                              AND tilt = ? AND azimuth = 0
                              AND weather_time >= ? AND weather_time <= ?
                            ORDER BY weather_time
                        """, (site_id, lat, lon, tilt, expected[0], expected[-1])).fetchall()
                        self.assertEqual(
                            [record[0] for record in records], expected,
                            f"{name}: {tilt} derece icin 72 saat verisi eksik"
                        )
                        return records

                    weather_original = read_weather(original_tilt)
                    weather_zero = read_weather(0)
                    weather_ninety = read_weather(90)

                    dc_kwp = panels * wp / 1000.0
                    totals = {"mevcut": 0.0, "yatay": 0.0, "dikey": 0.0}

                    for orig, flat, vertical in zip(
                        weather_original, weather_zero, weather_ninety
                    ):
                        temperature = float(orig[1])
                        common = dict(
                            air_temp=temperature,
                            dc_power_kwp=dc_kwp,
                            inverter_power_kw=float(ac_kw),
                            panel_age_years=float(years),
                        )
                        for key, record in (
                            ("mevcut", orig), ("yatay", flat), ("dikey", vertical)
                        ):
                            totals[key] += calculate_production(
                                radiation=float(record[2]), **common
                            )[0]

                    print(
                        f"{name}: {original_tilt:g} derece {totals['mevcut']:.2f} kWh | "
                        f"0 derece {totals['yatay']:.2f} kWh | "
                        f"90 derece {totals['dikey']:.2f} kWh (72 saat)"
                    )
                    self.assertGreater(totals["mevcut"], 0)
                    self.assertGreater(totals["yatay"], 0)
                    self.assertGreater(totals["dikey"], 0)
                    self.assertNotAlmostEqual(totals["yatay"], totals["dikey"], places=2)
                    self.assertNotAlmostEqual(totals["mevcut"], totals["dikey"], places=2)

    def test_uc_saha_ocak_temmuz(self):
        from collections import Counter
        from statistics import median

        db_file = Path(__file__).resolve().parent / "solar.db"
        if not db_file.is_file():
            self.skipTest("Yerel solar.db yok: mevsimsel test atlandi.")

        with closing(sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True)) as connection:
            has_table = connection.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'historical_weather_data'
            """).fetchone()
            if not has_table:
                self.skipTest("Tarihsel hava verisi tablosu yok: mevsimsel test atlandi.")

            loss_columns = (
                "soiling_loss", "reflection_loss", "mismatch_loss",
                "dc_cable_loss", "ac_cable_loss", "transformer_loss",
                "shading_loss", "availability_loss", "snow_loss",
            )

            for site_id, expected_name in ((12, "Saha 1"), (13, "Saha 2"), (14, "Saha 3")):
                with self.subTest(saha=expected_name):
                    site = connection.execute("""
                        SELECT name, latitude, longitude, tilt, azimuth,
                               panel_count, panel_power_wp, ac_power_kw, site_age_years
                        FROM sites WHERE id = ?
                    """, (site_id,)).fetchone()
                    self.assertIsNotNone(site, f"{expected_name}: saha bulunamadi")
                    name, lat, lon, tilt, azimuth, panels, wp, ac_kw, age = site
                    self.assertEqual(name, expected_name)
                    self.assertTrue(all(v is not None for v in (panels, wp, ac_kw, age)))

                    loss_row = connection.execute(
                        "SELECT " + ", ".join(loss_columns)
                        + " FROM site_losses WHERE site_id = ?", (site_id,)
                    ).fetchone()
                    losses = dict(zip(loss_columns, loss_row)) if loss_row else {}
                    dc_kwp = float(panels) * float(wp) / 1000.0
                    seasonal = {}

                    for month, label in ((1, "Ocak"), (7, "Temmuz")):
                        first = datetime(2026, month, 1)
                        last = datetime(2026, month + 1, 1)
                        expected_times = [
                            (first + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
                            for i in range(int((last - first).total_seconds() / 3600))
                        ]
                        weather = connection.execute("""
                            SELECT weather_time, temperature, tilted_radiation
                            FROM historical_weather_data
                            WHERE site_id = ? AND latitude = ? AND longitude = ?
                              AND tilt = ? AND azimuth = ?
                              AND weather_time >= ? AND weather_time < ?
                            ORDER BY weather_time
                        """, (
                            site_id, lat, lon, tilt, azimuth,
                            expected_times[0], last.strftime("%Y-%m-%dT%H:%M"),
                        )).fetchall()
                        self.assertEqual(
                            [item[0] for item in weather], expected_times,
                            f"{name}: {label} 2026 icin 744 saatlik veri eksik",
                        )

                        monthly_total = 0.0
                        daily_peaks = {}
                        for hour, temperature, radiation in weather:
                            self.assertIsNotNone(temperature, f"{name}: {hour} sicaklik eksik")
                            self.assertIsNotNone(radiation, f"{name}: {hour} isinim eksik")
                            energy, _ = calculate_production(
                                radiation=float(radiation),
                                air_temp=float(temperature),
                                dc_power_kwp=dc_kwp,
                                inverter_power_kw=float(ac_kw),
                                panel_age_years=float(age),
                                **losses,
                            )
                            self.assertGreaterEqual(energy, 0)
                            monthly_total += energy
                            day = hour[:10]
                            if day not in daily_peaks or energy > daily_peaks[day][0]:
                                daily_peaks[day] = (energy, int(hour[11:13]))

                        self.assertEqual(len(daily_peaks), 31)
                        peak_hours = [value[1] for value in daily_peaks.values()]
                        common_hour = Counter(peak_hours).most_common(1)[0][0]
                        median_hour = median(peak_hours)
                        self.assertGreater(monthly_total, 0)
                        self.assertGreaterEqual(median_hour, 9, f"{name}: {label} tepe saati cok erken")
                        self.assertLessEqual(median_hour, 18, f"{name}: {label} tepe saati cok gec")
                        seasonal[label] = monthly_total
                        print(
                            f"{name} {label}: {monthly_total:.2f} kWh | "
                            f"gunluk tepe saati (en sik): {common_hour:02d}:00 | "
                            f"ortanca tepe saati: {median_hour:.1f} | "
                            f"{len(expected_times)} saat"
                        )

                    self.assertGreater(
                        seasonal["Temmuz"], seasonal["Ocak"],
                        f"{name}: Temmuz toplam uretimi Ocak'tan yuksek degil",
                    )
                    print(
                        f"{name}: Temmuz / Ocak uretim orani = "
                        f"{seasonal['Temmuz'] / seasonal['Ocak']:.2f}"
                    )

    def test_uc_saha_antalya_trabzon(self):
        db_file = Path(__file__).resolve().parent / "solar.db"
        if not db_file.is_file():
            self.skipTest("Yerel solar.db yok: bolgesel test atlandi.")

        expected = [
            (datetime(2026, 7, 1) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
            for i in range(744)
        ]
        locations = {
            "Antalya": (36.8969, 30.7133),
            "Trabzon": (41.0027, 39.7168),
        }
        loss_columns = (
            "soiling_loss", "reflection_loss", "mismatch_loss",
            "dc_cable_loss", "ac_cable_loss", "transformer_loss",
            "shading_loss", "availability_loss", "snow_loss",
        )
        with closing(sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True)) as connection:
            table = connection.execute("""
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'historical_weather_data'
            """).fetchone()
            if not table:
                self.skipTest("historical_weather_data tablosu yok: bolgesel test atlandi.")

            site_details = {}
            for sid in (12, 13, 14):
                site = connection.execute("""
                    SELECT name, tilt, azimuth, panel_count, panel_power_wp,
                           ac_power_kw, site_age_years
                    FROM sites WHERE id = ?
                """, (sid,)).fetchone()
                self.assertIsNotNone(site, f"Saha ID {sid} bulunamadi")
                site_details[sid] = site

            self.assertEqual(
                (site_details[12][1], site_details[12][2]),
                (site_details[14][1], site_details[14][2]),
                "Saha 1 ve Saha 3 panel acilari farkli; veri paylasilamaz",
            )

            for sid, source_sid in ((12, 12), (13, 13), (14, 12)):
                name, tilt, azimuth, panels, wp, ac_kw, age = site_details[sid]
                with self.subTest(saha=name):
                    self.assertTrue(all(v is not None for v in (panels, wp, ac_kw, age)))
                    dc_kwp = float(panels) * float(wp) / 1000.0
                    loss_row = connection.execute(
                        "SELECT " + ", ".join(loss_columns)
                        + " FROM site_losses WHERE site_id = ?", (sid,)
                    ).fetchone()
                    losses = dict(zip(loss_columns, loss_row)) if loss_row else {}
                    totals = {}
                    for city, (latitude, longitude) in locations.items():
                        data = connection.execute("""
                            SELECT weather_time, temperature, tilted_radiation
                            FROM historical_weather_data
                            WHERE site_id = ? AND latitude = ? AND longitude = ?
                              AND tilt = ? AND azimuth = ?
                              AND weather_time >= ? AND weather_time <= ?
                            ORDER BY weather_time
                        """, (
                            source_sid, latitude, longitude, tilt, azimuth,
                            expected[0], expected[-1],
                        )).fetchall()
                        self.assertEqual(
                            [v[0] for v in data], expected,
                            f"{name}: {city} icin 744 saatlik veri eksik",
                        )
                        total_energy = 0.0
                        for _, temp, radiation in data:
                            self.assertIsNotNone(temp)
                            self.assertIsNotNone(radiation)
                            energy, _ = calculate_production(
                                radiation=float(radiation),
                                air_temp=float(temp),
                                dc_power_kwp=dc_kwp,
                                inverter_power_kw=float(ac_kw),
                                panel_age_years=float(age),
                                **losses,
                            )
                            self.assertGreaterEqual(energy, 0)
                            total_energy += energy
                        totals[city] = total_energy
                    self.assertGreater(totals["Trabzon"], 0)
                    print(
                        f"{name} Temmuz 2026: Antalya {totals['Antalya']:.2f} kWh | "
                        f"Trabzon {totals['Trabzon']:.2f} kWh | "
                        f"oran {totals['Antalya']/totals['Trabzon']:.2f}"
                    )
                    self.assertGreater(
                        totals["Antalya"], totals["Trabzon"],
                        f"{name}: Temmuz 2026'da Antalya beklenenden dusuk; hava verilerini incele",
                    )

    def test_uc_saha_yillik_uretim_kapasite_ve_clipping(self):
        db_file = Path(__file__).resolve().parent / "solar_yillik_test.db"
        if not db_file.is_file():
            self.skipTest(
                "Gecici 2025 veritabani yok; yillik test atlandi."
            )

        expected_start = "2025-01-01T00:00"
        expected_end = "2025-12-31T23:00"
        expected_hours = 8760
        loss_columns = (
            "soiling_loss", "reflection_loss", "mismatch_loss",
            "dc_cable_loss", "ac_cable_loss", "transformer_loss",
            "shading_loss", "availability_loss", "snow_loss",
        )
        clipping_percentages = {}

        with closing(sqlite3.connect(db_file.as_uri() + "?mode=ro", uri=True)) as connection:
            for site_id, expected_name in ((12, "Saha 1"), (13, "Saha 2"), (14, "Saha 3")):
                with self.subTest(saha=expected_name):
                    site = connection.execute("""
                        SELECT name, latitude, longitude, tilt, azimuth,
                               panel_count, panel_power_wp, ac_power_kw, site_age_years
                        FROM sites WHERE id = ?
                    """, (site_id,)).fetchone()
                    self.assertIsNotNone(site, f"{expected_name}: saha kaydi yok")
                    name, lat, lon, tilt, azimuth, panels, wp, ac_kw, age = site
                    self.assertEqual(name, expected_name)
                    self.assertTrue(all(v is not None for v in (
                        lat, lon, tilt, azimuth, panels, wp, ac_kw, age
                    )))

                    data = connection.execute("""
                        SELECT weather_time, temperature, tilted_radiation
                        FROM historical_weather_data
                        WHERE site_id = ? AND latitude = ? AND longitude = ?
                          AND tilt = ? AND azimuth = ?
                          AND weather_time >= ? AND weather_time <= ?
                        ORDER BY weather_time
                    """, (
                        site_id, lat, lon, tilt, azimuth,
                        expected_start, expected_end,
                    )).fetchall()
                    self.assertEqual(
                        len(data), expected_hours,
                        f"{name}: 2025 icin {len(data)}/{expected_hours} saat var",
                    )
                    for i, (hour, _, _) in enumerate(data):
                        expected_hour = (
                            datetime(2025, 1, 1) + timedelta(hours=i)
                        ).strftime("%Y-%m-%dT%H:%M")
                        self.assertEqual(hour, expected_hour, f"{name}: saat eksik / kaymis")

                    loss_row = connection.execute(
                        "SELECT " + ", ".join(loss_columns)
                        + " FROM site_losses WHERE site_id = ?", (site_id,)
                    ).fetchone()
                    losses = dict(zip(loss_columns, loss_row)) if loss_row else {}
                    dc_kwp = float(panels) * float(wp) / 1000.0
                    inverter_kw = float(ac_kw)
                    self.assertGreater(dc_kwp, 0)
                    self.assertGreater(inverter_kw, 0)

                    total_energy = 0.0
                    total_clipping = 0.0
                    monthly_clipping = {month: 0.0 for month in range(1, 13)}
                    for hour, temp, radiation in data:
                        self.assertIsNotNone(temp, f"{name} {hour}: sicaklik eksik")
                        self.assertIsNotNone(radiation, f"{name} {hour}: isinim eksik")
                        energy, clipping = calculate_production(
                            radiation=float(radiation),
                            air_temp=float(temp),
                            dc_power_kwp=dc_kwp,
                            inverter_power_kw=inverter_kw,
                            panel_age_years=float(age),
                            **losses,
                        )
                        self.assertGreaterEqual(energy, 0, f"{name}: negatif uretim")
                        self.assertLessEqual(energy, inverter_kw + 1e-6)
                        self.assertGreaterEqual(clipping, 0, f"{name}: negatif kirpma")
                        total_energy += energy
                        total_clipping += clipping
                        monthly_clipping[int(hour[5:7])] += clipping

                    specific_production = total_energy / dc_kwp  # kWh/kWp
                    capacity_factor = total_energy / (inverter_kw * expected_hours) * 100
                    clipping_share = (
                        total_clipping / (total_energy + total_clipping) * 100
                        if total_energy + total_clipping > 0 else 0.0
                    )
                    clipping_percentages[name] = clipping_share
                    peak_month = max(monthly_clipping, key=monthly_clipping.get)
                    print(
                        f"{name} 2025: Uretim {total_energy:,.2f} kWh | "
                        f"Spesifik {specific_production:.2f} kWh/kWp | "
                        f"AC kapasite faktoru %{capacity_factor:.2f} | "
                        f"Clipping {total_clipping:,.2f} kWh (%{clipping_share:.4f})"
                    )
                    print(
                        f"{name}: Aylik clipping (kWh): "
                        + ", ".join(
                            f"{month:02d}={monthly_clipping[month]:.2f}"
                            for month in range(1, 13)
                        )
                    )
                    print(
                        f"{name}: En yuksek aylik clipping: "
                        f"{peak_month:02d}. ay ({monthly_clipping[peak_month]:.2f} kWh)"
                    )
                    self.assertGreater(total_energy, 0)
                    self.assertGreater(specific_production, 0)
                    self.assertGreater(capacity_factor, 0)
                    self.assertLess(capacity_factor, 100)
                    self.assertGreaterEqual(clipping_share, 0)
                    self.assertLess(clipping_share, 100)

        self.assertGreater(
            clipping_percentages["Saha 2"], clipping_percentages["Saha 1"],
            "Yillik clipping Saha 2 > Saha 1 bekleniyordu; hava ve kayip parametrelerini incele",
        )
        self.assertGreater(
            clipping_percentages["Saha 1"], clipping_percentages["Saha 3"],
            "Yillik clipping Saha 1 > Saha 3 bekleniyordu; hava ve kayip parametrelerini incele",
        )

    def test_ozel_kayiplar(self):
        parametreler = dict(
            radiation=500,
            air_temp=25,
            dc_power_kwp=10,
            inverter_power_kw=8,
            panel_age_years=2,
        )
        normal, _ = calculate_production(**parametreler)
        ozel, _ = calculate_production(
            **parametreler,
            soiling_loss=0.03,
            reflection_loss=0.03,
            mismatch_loss=0.03,
            dc_cable_loss=0.03,
            shading_loss=0.03,
            snow_loss=0.03,
            ac_cable_loss=0.03,
            transformer_loss=0.03,
            availability_loss=0.02,
        )
        self.assertLess(ozel, normal)

    def test_toplam_kayip(self):
        self.assertAlmostEqual(
            calculate_total_loss([0.02, 0.03]),
            1 - (1 - 0.02) * (1 - 0.03),
        )


if __name__ == "__main__":
    unittest.main()
