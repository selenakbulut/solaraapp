def calculate_total_loss(losses):
    remaining_factor = 1.0

    for loss in losses:
        if not 0 <= loss < 1:
            raise ValueError("Kayıp oranı 0 ile 1 arasında olmalıdır.")

        remaining_factor *= (1 - loss)

    return 1 - remaining_factor


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
    temperature_coefficient = -0.004,
    dc_loss =0.05,
    soiling_loss=None,
    mismatch_loss=None,
    dc_cable_loss=None,
    shading_loss=None,
    snow_loss=None,
    ac_cable_loss=None,
    transformer_loss=None,
    availability_loss=None,
    reflection_loss=None
):
    individual_dc_losses = [
        soiling_loss,
        mismatch_loss,
        dc_cable_loss,
        shading_loss,
        snow_loss,
        reflection_loss
    ]

    if any(loss is not None for loss in individual_dc_losses):
        if not all(loss is not None for loss in individual_dc_losses):
            raise ValueError("DC kayıp kalemlerinin tamamı belirtilmelidir.")

        dc_loss = calculate_total_loss(individual_dc_losses)

    noct = 45
    ac_loss = 0.02

    individual_ac_losses = [
        ac_cable_loss,
        transformer_loss
    ]

    if any(loss is not None for loss in individual_ac_losses):

        if not all(loss is not None for loss in individual_ac_losses):
            raise ValueError(
                "AC kablo ve trafo kayıplarının ikisi de belirtilmelidir."
            )

        ac_loss = calculate_total_loss(individual_ac_losses)

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

    if availability_loss is not None:
        if not 0 <= availability_loss < 1:
            raise ValueError(
                "Kullanılabilirlik kaybı 0 ile 1 arasında olmalıdır."
            )

        final_energy_kwh *= (1 - availability_loss)

    return final_energy_kwh, clipping_loss_kwh
