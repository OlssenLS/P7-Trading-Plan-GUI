import requests
import pandas as pd

# --- Technical Indicator Calculation Functions ---
def calculate_ema(data, period):
    """Calculate Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()

def calculate_macd(data):
    """Calculate MACD (12,26,9)"""
    exp1 = data.ewm(span=12, adjust=False).mean()
    exp2 = data.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_stochastic(data, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator"""
    low_min = data['low'].rolling(window=k_period).min()
    high_max = data['high'].rolling(window=k_period).max()
    
    k = 100 * ((data['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()
    return k, d

def calculate_stochastic_golden_cross(data, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator and detect a golden cross."""
    low_min = data['low'].rolling(window=k_period).min()
    high_max = data['high'].rolling(window=k_period).max()
    
    k = 100 * ((data['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()

    if len(k) < 2 or len(d) < 2:
        return False # Not enough data for a cross

    # Golden cross: K crosses above D
    # K was below D in the previous period, and K is above D in the current period
    golden_cross = (k.iloc[-2] < d.iloc[-2]) & (k.iloc[-1] > d.iloc[-1])
    return golden_cross

def check_volume_criteria(data):
    """Check if volume is above 5-day high or 20-day high"""
    if len(data['volume']) < 20: # Ensure enough data for 20-day high
        return False 
    
    current_volume = data['volume'].iloc[-1]
    high_5_day = data['volume'].rolling(window=5).max().iloc[-2] # Use -2 to exclude current day's volume if it's part of the series being formed
    high_20_day = data['volume'].rolling(window=20).max().iloc[-2]
    
    return current_volume > high_5_day or current_volume > high_20_day

# --- Apply Technical Filters ---
def apply_technical_filters(df, filters):
    """Apply selected technical filters to the data"""
    if df.empty:
        return False

    meets_criteria = True
    latest_row = df.iloc[-1]
    
    if filters.get('ema_20'):
        ema20 = calculate_ema(df['close'], 20)
        meets_criteria &= latest_row['close'] > ema20.iloc[-1]

    if filters.get('ema_60'):
        ema60 = calculate_ema(df['close'], 60)
        meets_criteria &= latest_row['close'] > ema60.iloc[-1]

    if filters.get('macd'):
        macd, signal = calculate_macd(df['close'])
        meets_criteria &= macd.iloc[-1] > signal.iloc[-1]

    if filters.get('stochastic'):
        golden_cross = calculate_stochastic_golden_cross(df)
        meets_criteria &= golden_cross

    if filters.get('volume'):
        meets_criteria &= check_volume_criteria(df)

    return meets_criteria

# --- Generate Technical Analysis Summary ---
def get_technical_analysis_summary(df, filters):
    """Generate a summary of technical analysis based on selected filters only"""
    summary = []
    latest = df.iloc[-1]
    
    if filters.get('ema_20'):
        ema20 = calculate_ema(df['close'], 20)
        if latest['close'] > ema20.iloc[-1]:
            summary.append("Price above EMA20")
    
    if filters.get('ema_60'):
        ema60 = calculate_ema(df['close'], 60)
        if latest['close'] > ema60.iloc[-1]:
            summary.append("Price above EMA60")
    
    if filters.get('macd'):
        macd, signal = calculate_macd(df['close'])
        if macd.iloc[-1] > signal.iloc[-1]:
            summary.append("MACD above Signal")
    
    if filters.get('stochastic'):
        if calculate_stochastic_golden_cross(df):
            summary.append("Stochastic Golden Cross")
    
    if filters.get('volume'):
        current_volume = df['volume'].iloc[-1]
        if len(df['volume']) >= 5: # Check for 5-day high only if enough data
            high_5_day = df['volume'].rolling(window=5).max().shift(1).iloc[-1] # shift(1) to get previous high
            if current_volume > high_5_day:
                summary.append("Volume above 5-day high")
        
        if len(df['volume']) >= 20: # Check for 20-day high only if enough data
             high_20_day = df['volume'].rolling(window=20).max().shift(1).iloc[-1] # shift(1) to get previous high
             if current_volume > high_20_day and "Volume above 5-day high" not in summary: # Avoid duplicate message if also above 5-day
                summary.append("Volume above 20-day high")
        elif "Volume above 5-day high" not in summary and not (len(df['volume']) >= 5 and current_volume > df['volume'].rolling(window=5).max().shift(1).iloc[-1]): # If not already added and not enough data for 20 day
             # Check if any volume criteria could be met at all based on data length
            if not (len(df['volume']) >= 5 and current_volume > df['volume'].rolling(window=5).max().shift(1).iloc[-1]) and \
               not (len(df['volume']) >= 20 and current_volume > df['volume'].rolling(window=20).max().shift(1).iloc[-1]):
                 pass # No message if no criteria can be met or already added.
    
    return ", ".join(summary) if summary else "No significant technical signals" 