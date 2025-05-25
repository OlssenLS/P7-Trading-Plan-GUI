def adjust_price_by_fraction(price):
    """
    Adjusts a given price based on IDX BEI price fraction rules.

    Args:
        price (float or int): The original price.

    Returns:
        int: The adjusted price, rounded to the nearest valid fraction.
    """
    price = float(price) # Ensure price is float for comparisons
    fraction = get_fraction_for_price(price) # Use helper

    # Adjust the price to the nearest multiple of the fraction
    # For upward adjustment (e.g., for entry prices, take profit)
    # adjusted_price = (price + fraction - 1) // fraction * fraction # if we always want to round up to next fraction
    # For rounding to nearest:
    adjusted_price = round(price / fraction) * fraction
    
    return int(adjusted_price)

def get_fraction_for_price(price):
    """
    Determines the IDX BEI price fraction for a given price.

    Args:
        price (float or int): The price.

    Returns:
        int: The fraction size.
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
    Assumes base_price is already an adjusted price (i.e., aligns with a fraction).

    Args:
        base_price (float or int): The starting price, assumed to be adjusted.
        num_ticks (int): The number of ticks to add.

    Returns:
        int: The new price after adding the ticks.
    """
    current_price = float(base_price)
    for _ in range(num_ticks):
        tick_size = get_fraction_for_price(current_price)
        current_price += tick_size
    return int(current_price)