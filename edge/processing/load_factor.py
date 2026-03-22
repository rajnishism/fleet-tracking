# load_factor.py

"""
Mining Truck Load Factor + Fuel Model

Inputs:
- speed (km/h)
- vmax (km/h)
- is_loaded (1 = loaded, 0 = empty)
- slope:
    +1 = uphill
     0 = flat
    -1 = downhill
"""

def get_base_load_factor(is_loaded: int, slope: int) -> float:
    """
    Base load factor depends on payload and slope

    is_loaded:
        1 = loaded
        0 = empty

    slope:
        +1 = uphill
         0 = flat
        -1 = downhill
    """

    # Loaded cases
    if is_loaded == 1:
        if slope == 1:   # uphill
            return 0.7
        elif slope == 0: # flat
            return 0.5
        elif slope == -1: # downhill
            return 0.2

    # Empty cases
    else:
        if slope == 1:
            return 0.5
        elif slope == 0:
            return 0.3
        elif slope == -1:
            return 0.1

    return 0.3  # fallback


def get_speed_factor(slope: int) -> float:
    """
    Speed influence factor (k)

    Higher on uphill because engine works harder
    Lower on downhill due to gravity assist
    """
    if slope == 1:
        return 0.3
    elif slope == 0:
        return 0.25
    elif slope == -1:
        return 0.2

    return 0.25


def compute_load_factor(speed: float, vmax: float, is_loaded: int, slope: int) -> float:
    """
    Load Factor Model:
    LF = baseLF + k * (speed / vmax)

    Clamped between 0 and 1
    """

    if vmax <= 0:
        raise ValueError("vmax must be greater than 0")

    base_lf = get_base_load_factor(is_loaded, slope)
    k = get_speed_factor(slope)

    lf = base_lf + k * (speed / vmax)

    # Clamp LF to [0, 1]
    lf = max(0.0, min(lf, 1.0))

    return lf


#  REAL FUEL MODEL (Physics-based)
def compute_fuel_rate(engine_power_kw: float, lf: float, sfc: float = 0.22) -> float:
    """
    Fuel Rate (L/hr)

    engine_power_kw → Rated engine power
    lf → Load factor
    sfc → Specific fuel consumption (default = 0.22 L/kW/hr)
    """

    return lf * engine_power_kw * sfc


