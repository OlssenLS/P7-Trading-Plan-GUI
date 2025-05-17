import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

# Get the script directory for file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Constants for data paths and break tracking
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
STOCKS_FILE = os.path.join(SCRIPT_DIR, "stocks.txt")
DETECTION_HISTORY_FILE = os.path.join(DATA_DIR, "detection_history.json")
KEEP_5D_BREAK_DAYS = 3
KEEP_1M_BREAK_DAYS = 5
KEEP_2M_BREAK_DAYS = 6
KEEP_3M_BREAK_DAYS = 7

def get_stock_list():
    """Read stock list from stocks.txt"""
    stock_list = []
    try:
        # Ensure data directory exists, as STOCKS_FILE is within SCRIPT_DIR but related to data logic
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(STOCKS_FILE):
             # Create a default stocks.txt if it doesn't exist, useful if app is run directly
            default_stocks = [
                "BBCA", "BBRI", "BMRI", "TLKM", "ASII",
                "UNVR", "INDF", "ICBP", "SMGR", "CPIN"
            ]
            with open(STOCKS_FILE, "w") as f:
                f.write("\n".join(default_stocks))
            print(f"Created default stocks.txt at {STOCKS_FILE}")

        with open(STOCKS_FILE, "r") as f:
            stock_list = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        print(f"Error reading or creating stocks.txt: {e}")
    return stock_list

def load_detection_history():
    """Load detection history from file if it exists"""
    history = {}
    try:
        os.makedirs(DATA_DIR, exist_ok=True) # Ensure data directory exists before loading
        if os.path.exists(DETECTION_HISTORY_FILE):
            with open(DETECTION_HISTORY_FILE, "r") as f:
                history = json.load(f)
    except Exception as e:
        print(f"Error loading detection history: {e}")
    return history

def save_detection_history(history):
    """Save detection history to file"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True) # Ensure data directory exists before saving
        with open(DETECTION_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"Error saving detection history: {e}")

def detect_break_high_price(options, output_list_for_plan, progress_callback, completion_callback, set_continue_button_state_callback):
    """Detect break high price based on selected options and update UI via callbacks."""
    base_url = "https://yfinance-web-indonesia-data.vercel.app"
    
    # Initialize DATA_DIR and STOCKS_FILE creation/check here as well,
    # to ensure they exist when running this module, e.g. for tests or if main.py's init didn't run.
    os.makedirs(DATA_DIR, exist_ok=True)
    stocks = get_stock_list() # This will also ensure stocks.txt exists
    
    output_list_for_plan.clear()
    set_continue_button_state_callback(False)
    
    if not any(options.values()):
        progress_callback("Please select at least one period option.\n")
        completion_callback([], "Please select at least one period option.\n", "") # Pass empty list for detected_stocks
        return
    
    progress_callback("Starting detection...\n")
    if not stocks:
        message = "Stock list is empty. Please check stocks.txt.\n"
        progress_callback(message)
        completion_callback([], message, "Detection aborted.")
        return
        
    progress_callback(f"Total stocks to check: {len(stocks)}\n")
    
    detection_history = load_detection_history()
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    if current_date not in detection_history:
        detection_history[current_date] = {}
        
    dates = sorted(list(detection_history.keys()))
    if len(dates) > 10:
        for old_date in dates[:-10]:
            if old_date in detection_history:
                del detection_history[old_date]
    
    detected_stocks_for_processing = [] 
    
    for stock in stocks:
        try:
            endpoint_url = f"{base_url}/api/stocks/{stock}?start_date=2023-01-01" # Use a reasonable start_date
            progress_callback(f"Checking {stock}...\n")
            
            response = requests.get(endpoint_url, timeout=10) # Added timeout
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "historical_data" in data and data["historical_data"] and len(data["historical_data"]) > 0:
                    progress_callback(f"  Got data for {stock} ({len(data['historical_data'])} records)\n")
                    
                    df = pd.DataFrame(data["historical_data"])
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date")
                    
                    if df.empty:
                        progress_callback(f"  No historical data rows for {stock} after processing.\n")
                        continue

                    latest_close = df.iloc[-1]["close"]
                    latest_date = df.iloc[-1]["date"]
                    latest_date_str = latest_date.strftime("%Y-%m-%d")
                    
                    debug_message = f"\n{stock} - Latest close: {latest_close:.2f} on {latest_date_str}\n"
                    progress_callback(debug_message)
                    
                    available_dates = sorted(df["date"].unique())
                    broke_high = False
                    break_reasons = []
                    break_types = {} # Stores break_date and days_since for current run
                    high_prices_for_stock = {} # Stores actual high prices for new breaks this run

                    # 5-day high
                    if options["5_days"] and len(df) >= 6:
                        is_new_break_5d = False
                        current_period_high_5d = df["high"].iloc[-6:-1].max() # High of previous 5 days

                        if latest_close > current_period_high_5d:
                            is_new_break_5d = True
                            break_types["5d_break_date"] = latest_date_str
                            high_prices_for_stock["5d"] = current_period_high_5d
                            progress_callback(f"  NEW 5-day high break: {current_period_high_5d:.2f}, Close: {latest_close:.2f}\n")
                        
                        is_continued_break_5d = False
                        if not is_new_break_5d and stock in detection_history.get(current_date, {}):
                            stock_hist = detection_history[current_date].get(stock, {})
                            if "5d_break_date" in stock_hist:
                                hist_break_date = datetime.strptime(stock_hist["5d_break_date"], "%Y-%m-%d").date()
                                days_since = (latest_date.date() - hist_break_date).days
                                if 0 <= days_since <= KEEP_5D_BREAK_DAYS: # Allow same day as continued
                                    is_continued_break_5d = True
                                    break_types["5d_break_date"] = stock_hist["5d_break_date"] # Preserve original break date
                                    break_types["5d_days_since"] = days_since
                                    high_prices_for_stock["5d"] = stock_hist.get("high_prices",{}).get("5d", current_period_high_5d)
                                    progress_callback(f"  CONTINUED 5-day high break (Day {days_since})\n")
                        
                        if is_new_break_5d or is_continued_break_5d:
                            broke_high = True
                            if "5d_days_since" in break_types:
                                break_reasons.append(f"5 Days High (Day {break_types['5d_days_since']} of {KEEP_5D_BREAK_DAYS})")
                            else:
                                break_reasons.append("5 Days High (New Break)")

                    # 1-month high
                    if options["1_month"] and len(df) >= 22: # Approx 22 trading days + current
                        is_new_break_1m = False
                        current_period_high_1m = df["high"].iloc[-22:-1].max()

                        if latest_close > current_period_high_1m:
                            is_new_break_1m = True
                            break_types["1m_break_date"] = latest_date_str
                            high_prices_for_stock["1m"] = current_period_high_1m
                            progress_callback(f"  NEW 1-month high break: {current_period_high_1m:.2f}, Close: {latest_close:.2f}\n")

                        is_continued_break_1m = False
                        if not is_new_break_1m and stock in detection_history.get(current_date, {}):
                            stock_hist = detection_history[current_date].get(stock, {})
                            if "1m_break_date" in stock_hist:
                                hist_break_date = datetime.strptime(stock_hist["1m_break_date"], "%Y-%m-%d").date()
                                days_since = (latest_date.date() - hist_break_date).days
                                if 0 <= days_since <= KEEP_1M_BREAK_DAYS:
                                    is_continued_break_1m = True
                                    break_types["1m_break_date"] = stock_hist["1m_break_date"]
                                    break_types["1m_days_since"] = days_since
                                    high_prices_for_stock["1m"] = stock_hist.get("high_prices",{}).get("1m", current_period_high_1m)
                                    progress_callback(f"  CONTINUED 1-month high break (Day {days_since})\n")

                        if is_new_break_1m or is_continued_break_1m:
                            broke_high = True
                            if "1m_days_since" in break_types:
                                break_reasons.append(f"1 Month High (Day {break_types['1m_days_since']} of {KEEP_1M_BREAK_DAYS})")
                            else:
                                break_reasons.append("1 Month High (New Break)")
                    
                    # 2-months high
                    if options["2_months"] and len(df) >= 44: # Approx 44 trading days + current
                        is_new_break_2m = False
                        current_period_high_2m = df["high"].iloc[-44:-1].max()

                        if latest_close > current_period_high_2m:
                            is_new_break_2m = True
                            break_types["2m_break_date"] = latest_date_str
                            high_prices_for_stock["2m"] = current_period_high_2m
                            progress_callback(f"  NEW 2-months high break: {current_period_high_2m:.2f}, Close: {latest_close:.2f}\n")

                        is_continued_break_2m = False
                        if not is_new_break_2m and stock in detection_history.get(current_date, {}):
                            stock_hist = detection_history[current_date].get(stock, {})
                            if "2m_break_date" in stock_hist:
                                hist_break_date = datetime.strptime(stock_hist["2m_break_date"], "%Y-%m-%d").date()
                                days_since = (latest_date.date() - hist_break_date).days
                                if 0 <= days_since <= KEEP_2M_BREAK_DAYS:
                                    is_continued_break_2m = True
                                    break_types["2m_break_date"] = stock_hist["2m_break_date"]
                                    break_types["2m_days_since"] = days_since
                                    high_prices_for_stock["2m"] = stock_hist.get("high_prices",{}).get("2m", current_period_high_2m)
                                    progress_callback(f"  CONTINUED 2-months high break (Day {days_since})\n")
                        
                        if is_new_break_2m or is_continued_break_2m:
                            broke_high = True
                            if "2m_days_since" in break_types:
                                break_reasons.append(f"2 Months High (Day {break_types['2m_days_since']} of {KEEP_2M_BREAK_DAYS})")
                            else:
                                break_reasons.append("2 Months High (New Break)")

                    # 3-months high
                    if options["3_months"] and len(df) >= 66: # Approx 66 trading days + current
                        is_new_break_3m = False
                        current_period_high_3m = df["high"].iloc[-66:-1].max()

                        if latest_close > current_period_high_3m:
                            is_new_break_3m = True
                            break_types["3m_break_date"] = latest_date_str
                            high_prices_for_stock["3m"] = current_period_high_3m
                            progress_callback(f"  NEW 3-months high break: {current_period_high_3m:.2f}, Close: {latest_close:.2f}\n")

                        is_continued_break_3m = False
                        if not is_new_break_3m and stock in detection_history.get(current_date, {}):
                            stock_hist = detection_history[current_date].get(stock, {})
                            if "3m_break_date" in stock_hist:
                                hist_break_date = datetime.strptime(stock_hist["3m_break_date"], "%Y-%m-%d").date()
                                days_since = (latest_date.date() - hist_break_date).days
                                if 0 <= days_since <= KEEP_3M_BREAK_DAYS:
                                    is_continued_break_3m = True
                                    break_types["3m_break_date"] = stock_hist["3m_break_date"]
                                    break_types["3m_days_since"] = days_since
                                    high_prices_for_stock["3m"] = stock_hist.get("high_prices",{}).get("3m", current_period_high_3m)
                                    progress_callback(f"  CONTINUED 3-months high break (Day {days_since})\n")

                        if is_new_break_3m or is_continued_break_3m:
                            broke_high = True
                            if "3m_days_since" in break_types:
                                break_reasons.append(f"3 Months High (Day {break_types['3m_days_since']} of {KEEP_3M_BREAK_DAYS})")
                            else:
                                break_reasons.append("3 Months High (New Break)")
                    
                    if broke_high:
                        detected_stocks_for_processing.append((stock, break_reasons, latest_close, high_prices_for_stock))
                        
                        # Update history for this stock for today
                        if stock not in detection_history[current_date]:
                            detection_history[current_date][stock] = {}
                        
                        # Persist break types (dates, days_since) and associated high prices
                        for key, value in break_types.items():
                             detection_history[current_date][stock][key] = value
                        if high_prices_for_stock: # only save if there are new highs determined
                            detection_history[current_date][stock]["high_prices"] = {**detection_history[current_date][stock].get("high_prices",{}), **high_prices_for_stock}


                elif isinstance(data, dict) and data.get("message") == "No data found":
                     progress_callback(f"  No data found for {stock} via API.\n")
                else:
                    progress_callback(f"  Unexpected data structure or empty historical_data for {stock}.\n")
            else:
                progress_callback(f"  API error for {stock}: {response.status_code} {response.text}\n")
            
        except requests.exceptions.Timeout:
            progress_callback(f"Error processing {stock}: Request timed out.\n")
        except Exception as e:
            progress_callback(f"Error processing {stock}: {str(e)}\n")
    
    save_detection_history(detection_history)
    output_list_for_plan.extend(detected_stocks_for_processing)

    summary_text_parts = []
    if detected_stocks_for_processing:
        summary_text_parts.append("Detected stocks breaking high price:\n\n")
        for stock_name, reasons, close, highs_info in detected_stocks_for_processing:
            summary_text_parts.append(f"{stock_name}: {', '.join(reasons)} - Close: {close:.2f}\n")
            # Add high price information for each break type
            if highs_info: # Check if highs_info is not empty
                for reason_text in reasons: # Iterate through the reasons to decide which high to print
                    if "5 Days" in reason_text and "5d" in highs_info:
                        summary_text_parts.append(f"    5 Days High: {highs_info['5d']:.2f}\n")
                    if "1 Month" in reason_text and "1m" in highs_info:
                        summary_text_parts.append(f"    1 Month High: {highs_info['1m']:.2f}\n")
                    if "2 Months" in reason_text and "2m" in highs_info:
                        summary_text_parts.append(f"    2 Months High: {highs_info['2m']:.2f}\n")
                    if "3 Months" in reason_text and "3m" in highs_info:
                        summary_text_parts.append(f"    3 Months High: {highs_info['3m']:.2f}\n")
            summary_text_parts.append("\n")
    else:
        summary_text_parts.append("No stocks breaking high price detected.\n")
    
    final_status_message = f"\nDetection complete. Found {len(detected_stocks_for_processing)} stocks breaking high price.\n"
    
    completion_callback(detected_stocks_for_processing, "".join(summary_text_parts), final_status_message)

    if detected_stocks_for_processing:
        set_continue_button_state_callback(True)
    # No explicit else to disable button, it's handled by the initial set_continue_button_state_callback(False)
    # and only enabled if stocks are found. 