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

def check_volume_criteria(data):
    """Check if volume is above average"""
    avg_volume = data['volume'].rolling(window=20).mean()
    return data['volume'] > avg_volume

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
        k, d = calculate_stochastic(df)
        meets_criteria &= 20 <= k.iloc[-1] <= 80 and 20 <= d.iloc[-1] <= 80

    if filters.get('volume'):
        meets_criteria &= check_volume_criteria(df).iloc[-1]

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
        k, d = calculate_stochastic(df)
        stoch_k = k.iloc[-1]
        stoch_d = d.iloc[-1]
        if 20 <= stoch_k <= 80 and 20 <= stoch_d <= 80:
            summary.append("Stochastic in neutral zone")
    
    if filters.get('volume'):
        volume_above_avg = check_volume_criteria(df)
        if volume_above_avg.iloc[-1]:
            summary.append("Volume above 20-day average")
    
    return ", ".join(summary) if summary else "No significant technical signals" 