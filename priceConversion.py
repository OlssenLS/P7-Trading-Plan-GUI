# --- Price Adjustment and Fraction Logic (IDX BEI Rules) ---
def adjust_price_by_fraction(price):
    """
    Adjusts a given price based on IDX BEI price fraction rules.
    Returns: The adjusted price, rounded to the nearest valid fraction.
    """
    price = float(price)
    fraction = get_fraction_for_price(price)
    adjusted_price = round(price / fraction) * fraction
    return int(adjusted_price)

def get_fraction_for_price(price):
    """
    Determines the IDX BEI price fraction for a given price.
    Returns: The fraction size.
    """
    price = float(price)
    if price < 200:
        return 1
    elif 200 <= price < 500:
        return 2
    elif 500 <= price < 2000:
        return 5
    elif 2000 <= price < 5000:
        return 10
    else: # price >= 5000
        return 25

def add_ticks_to_price(base_price, num_ticks):
    """
    Adds a specified number of ticks to a base price, adhering to IDX BEI fraction rules.
    Assumes base_price is already an adjusted price.
    Returns: The new price after adding the ticks.
    """
    current_price = float(base_price)
    for _ in range(num_ticks):
        tick_size = get_fraction_for_price(current_price)
        current_price += tick_size
    return int(current_price)