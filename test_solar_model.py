import unittest

from solar_model import calculate_production


class TestSolarModel(unittest.TestCase):

    def test_night_production(self):

        energy, clipping = calculate_production(
            radiation=0,
            air_temp=20,
            dc_power_kwp=10,
            inverter_power_kw=8,
            panel_age_years=0
        )

        self.assertEqual(energy, 0)
        self.assertEqual(clipping, 0)

    def test_temperature(self):

        energy_cold, _ = calculate_production(
            radiation=800,
            air_temp=15,
            dc_power_kwp=10,
            inverter_power_kw=8,
            panel_age_years=0
        )

        energy_hot, _ = calculate_production(
            radiation=800,
            air_temp=40,
            dc_power_kwp=10,
            inverter_power_kw=8,
            panel_age_years=0
        )

        self.assertLess(energy_hot, energy_cold)

    def test_aging(self):
        energy_new, _ = calculate_production(
            radiation=800,
            air_temp=25,
            dc_power_kwp=10,
            inverter_power_kw=8,
            panel_age_years=0
        )

        energy_old, _ = calculate_production(
            radiation=800,
            air_temp=25,
            dc_power_kwp=10,
            inverter_power_kw=8,
            panel_age_years=15
        )

        self.assertLess(energy_old, energy_new)

    def test_inverter_clipping(self):

        energy, clipping = calculate_production(
            radiation=1000,
            air_temp=25,
            dc_power_kwp=20,
            inverter_power_kw=4,
            panel_age_years=0
        )

        self.assertLessEqual(energy, 4)
        self.assertGreater(clipping, 0)

if __name__ == "__main__":
    unittest.main()