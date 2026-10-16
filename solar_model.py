
def calculate_inverter_efficiency(dc_power_kw, inverter_power_kw):
    if dc_power_kw <= 0:
        return 0

    load_ratio = dc_power_kw / inverter_power_kw

    if load_ratio < 0.10:
        return 0.85
    elif load_ratio < 0.25:
        return 0.90
    elif load_ratio < 0.50:
        return 0.94
    elif load_ratio < 0.75:
        return 0.96
    else:
        return 0.97


def calculate_production(
    radiation,
    air_temp,
    dc_power_kwp,
    inverter_power_kw,
    panel_age_years,
    temperature_coefficient = -0.004
):
    noct = 45
    dc_loss = 0.05
    ac_loss = 0.02
    annual_degradation = 0.005

    age_factor = (1 - annual_degradation) ** panel_age_years

    cell_temp = air_temp + ((noct - 20) / 800) * radiation

    temp_factor = 1 + temperature_coefficient * (cell_temp - 25)

    dc_power_kw = max(
        0,
        dc_power_kwp * (radiation / 1000) * temp_factor
        * age_factor * (1 - dc_loss)
    )

    efficiency = calculate_inverter_efficiency(
        dc_power_kw,
        inverter_power_kw
    )
    potential_ac_power_kw = dc_power_kw * efficiency

    clipping_loss_kwh = max(
        0,
        potential_ac_power_kw - inverter_power_kw
    ) * (1 - ac_loss)

    ac_power_kw = min(
        dc_power_kw * efficiency,
        inverter_power_kw
    )

    final_energy_kwh = ac_power_kw * (1 - ac_loss)

    return final_energy_kwh, clipping_loss_kwh
