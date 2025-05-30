import pandas as pd

# --- Technical Indicator Calculation Functions ---
async def calculate_ema(data, period):
    """Calculate Exponential Moving Average"""
    return data.ewm(span=period, adjust=False).mean()

async def calculate_macd(data):
    """Calculate MACD (12,26,9)"""
    exp1 = await calculate_ema(data, 12) # Assuming calculate_ema is async
    exp2 = await calculate_ema(data, 26) # Assuming calculate_ema is async
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean() # ewm().mean() is pandas, not easily async here
    return macd, signal

async def calculate_stochastic(data, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator"""
    low_min = data['low'].rolling(window=k_period).min()
    high_max = data['high'].rolling(window=k_period).max()
    
    k = 100 * ((data['close'] - low_min) / (high_max - low_min))
    d = k.rolling(window=d_period).mean()
    return k, d

async def calculate_stochastic_golden_cross(data, k_period=14, d_period=3):
    """Calculate Stochastic Oscillator and detect a golden cross."""
    # This function's internal pandas operations remain synchronous
    # but it's called by other async functions.
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

async def check_volume_criteria(data):
    """Check if volume is above 5-day high or 20-day high"""
    if len(data['volume']) < 20: # Ensure enough data for 20-day high
        # If less than 20 days, check for 5-day high if possible
        if len(data['volume']) >= 5:
            current_volume = data['volume'].iloc[-1]
            high_5_day = data['volume'].rolling(window=5).max().iloc[-2] 
            return current_volume > high_5_day
        return False 
    
    current_volume = data['volume'].iloc[-1]
    high_5_day = data['volume'].rolling(window=5).max().iloc[-2]
    high_20_day = data['volume'].rolling(window=20).max().iloc[-2]
    
    return current_volume > high_5_day or current_volume > high_20_day

# --- Apply Technical Filters ---
async def apply_technical_filters(df, technical_options):
    """Apply selected technical filters to the data"""
    passed_all = True
    passed_reasons = []
    failed_details = []

    if df.empty:
        return {"passed_all_selected_technical_filters": False, "passed_filters_reasons": [], "failed_filters_details": ["DataFrame is empty"]}

    latest_row = df.iloc[-1]
    
    # Standard EMA filters (if not in advanced custom mode)
    if not technical_options.get("use_custom_ema"):
        if technical_options.get('ema_20'):
            ema20 = await calculate_ema(df['close'], 20)
            if not (latest_row['close'] > ema20.iloc[-1]):
                passed_all = False
                failed_details.append("Price not > EMA20")
            else:
                passed_reasons.append("Price > EMA20")

        if technical_options.get('ema_60'):
            ema60 = await calculate_ema(df['close'], 60)
            if not (latest_row['close'] > ema60.iloc[-1]):
                passed_all = False
                failed_details.append("Price not > EMA60")
            else:
                passed_reasons.append("Price > EMA60")
    
    # Custom EMA filters from Advanced Mode
    if technical_options.get("use_custom_ema"):
        try:
            ema1_period_str = technical_options.get("ema1_period")
            ema2_period_str = technical_options.get("ema2_period")

            if ema1_period_str and ema2_period_str: # Ensure both are provided
                ema1_period = int(ema1_period_str)
                ema2_period = int(ema2_period_str)

                if ema1_period > 0:
                    ema_custom_1_val = await calculate_ema(df['close'], ema1_period)
                    if not (latest_row['close'] > ema_custom_1_val.iloc[-1]):
                        passed_all = False
                        failed_details.append(f"Price not > Custom EMA{ema1_period}")
                    else:
                        passed_reasons.append(f"Price > Custom EMA{ema1_period}")
                
                if ema2_period > 0:
                    # Assuming for custom EMA2, we also check if price is above it.
                    # The logic might differ (e.g., price between EMA1 and EMA2, or EMA1 > EMA2)
                    # For now, keeping it simple: Price > EMA for both if specified.
                    ema_custom_2_val = await calculate_ema(df['close'], ema2_period)
                    if not (latest_row['close'] > ema_custom_2_val.iloc[-1]): 
                        passed_all = False
                        failed_details.append(f"Price not > Custom EMA{ema2_period}")
                    else:
                        passed_reasons.append(f"Price > Custom EMA{ema2_period}")
            else:
                # This case should ideally be caught earlier if 'use_custom_ema' is true
                # but periods are missing. FilterManager should ensure they are set.
                failed_details.append("Custom EMA periods not fully specified.")
                # passed_all = False # Optionally mark as failed if crucial

        except ValueError:
            passed_all = False
            failed_details.append("Invalid custom EMA period value(s).")
        except Exception as e:
            passed_all = False
            failed_details.append(f"Error processing custom EMAs: {str(e)}")

    if technical_options.get('macd'):
        macd, signal = await calculate_macd(df['close'])
        if not (macd.iloc[-1] > signal.iloc[-1]):
            passed_all = False
            failed_details.append("MACD not > Signal")
        else:
            passed_reasons.append("MACD > Signal")

    if technical_options.get('stochastic'):
        golden_cross = await calculate_stochastic_golden_cross(df)
        if not golden_cross:
            passed_all = False
            failed_details.append("No Stochastic Golden Cross")
        else:
            passed_reasons.append("Stochastic Golden Cross")

    if technical_options.get('volume'):
        volume_ok = await check_volume_criteria(df)
        if not volume_ok:
            passed_all = False
            failed_details.append("Volume criteria not met")
        else:
            passed_reasons.append("Volume criteria met")

    return {"passed_all_selected_technical_filters": passed_all, "passed_filters_reasons": passed_reasons, "failed_filters_details": failed_details}

# --- Generate Technical Analysis Summary ---
async def get_technical_analysis_summary(df, technical_options):
    """Generate a summary of technical analysis based on selected filters only"""
    summary = []
    if df.empty:
        return "No data for TA summary"
        
    latest = df.iloc[-1]
    
    # Standard EMA filters
    if not technical_options.get("use_custom_ema"):
        if technical_options.get('ema_20'):
            ema20 = await calculate_ema(df['close'], 20)
            if latest['close'] > ema20.iloc[-1]:
                summary.append("Price > EMA20")
        
        if technical_options.get('ema_60'):
            ema60 = await calculate_ema(df['close'], 60)
            if latest['close'] > ema60.iloc[-1]:
                summary.append("Price > EMA60")

    # Custom EMA filters from Advanced Mode
    if technical_options.get("use_custom_ema"):
        try:
            ema1_period_str = technical_options.get("ema1_period")
            ema2_period_str = technical_options.get("ema2_period")

            if ema1_period_str and ema2_period_str:
                ema1_period = int(ema1_period_str)
                ema2_period = int(ema2_period_str)

                if ema1_period > 0:
                    ema_custom_1_val = await calculate_ema(df['close'], ema1_period)
                    if latest['close'] > ema_custom_1_val.iloc[-1]:
                        summary.append(f"Price > Custom EMA{ema1_period}")
                
                if ema2_period > 0:
                    ema_custom_2_val = await calculate_ema(df['close'], ema2_period)
                    if latest['close'] > ema_custom_2_val.iloc[-1]:
                        summary.append(f"Price > Custom EMA{ema2_period}")
        except ValueError:
            summary.append("Invalid custom EMA period value(s) for summary.")
        except Exception as e:
            summary.append(f"Error in custom EMA summary: {str(e)}")
    
    if technical_options.get('macd'):
        macd, signal = await calculate_macd(df['close'])
        if macd.iloc[-1] > signal.iloc[-1]:
            summary.append("MACD > Signal")
    
    if technical_options.get('stochastic'):
        if await calculate_stochastic_golden_cross(df):
            summary.append("Stochastic Golden Cross")
    
    if technical_options.get('volume'):
        current_volume = df['volume'].iloc[-1]
        # rolling(W).max().iloc[-2] gets the max of W-day window ending at the previous day.
        # Ensure enough data for .iloc[-2] access from rolling max (needs W values for rolling, +1 for prev day).
        
        added_5_day_msg = False
        if len(df['volume']) >= 5 + 1: 
            high_5_day_prev = df['volume'].rolling(window=5).max().iloc[-2]
            if pd.notna(high_5_day_prev) and current_volume > high_5_day_prev:
                summary.append("Volume above 5-day high")
                added_5_day_msg = True
        
        if not added_5_day_msg and len(df['volume']) >= 20 + 1: 
            high_20_day_prev = df['volume'].rolling(window=20).max().iloc[-2]
            if pd.notna(high_20_day_prev) and current_volume > high_20_day_prev:
                summary.append("Volume above 20-day high")
    
    return ", ".join(summary) if summary else "No significant technical signals" 