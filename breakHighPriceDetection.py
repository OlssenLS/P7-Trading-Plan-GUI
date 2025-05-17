import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures # Added for threading

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

def fetch_and_process_stock_data(stock, options, base_url, current_date_history, latest_date_for_run_dt):
    """Fetches and processes data for a single stock. Designed to be run in a thread."""
    try:
        endpoint_url = f"{base_url}/api/stocks/{stock}?start_date=2023-01-01"
        # progress_callback(f"Checking {stock}...\n") # Progress callback will be called from main thread based on status
        
        response = requests.get(endpoint_url, timeout=15) # Increased timeout slightly for threaded env
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "historical_data" in data and data["historical_data"] and len(data["historical_data"]) > 0:
                # progress_callback(f"  Got data for {stock} ({len(data['historical_data'])} records)\n")
                
                df = pd.DataFrame(data["historical_data"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                
                if df.empty:
                    # progress_callback(f"  No historical data rows for {stock} after processing.\n")
                    return stock, None, f"No historical data for {stock}."

                latest_close = df.iloc[-1]["close"]
                latest_date_df = df.iloc[-1]["date"]
                # Ensure latest_date_df is comparable with latest_date_for_run_dt (both should be datetime objects)
                # latest_date_for_run_dt is passed as datetime.date, convert latest_date_df to date for comparison if needed or ensure consistency
                # For simplicity, this example assumes direct comparison or that types are handled prior/post this function.
                # For the purpose of break detection, we use the latest data from the stock's own history.
                latest_date_str = latest_date_df.strftime("%Y-%m-%d")
                
                # debug_message = f"\n{stock} - Latest close: {latest_close:.2f} on {latest_date_str}\n"
                # progress_callback(debug_message)
                
                broke_high = False
                break_reasons = []
                break_types_for_history = {} # Stores break_date and days_since for current run history
                high_prices_for_stock_output = {} # Stores actual high prices for new breaks for output summary

                stock_hist_today = current_date_history.get(stock, {})

                # 5-day high
                if options["5_days"] and len(df) >= 6:
                    is_new_break_5d = False
                    current_period_high_5d = df["high"].iloc[-6:-1].max()
                    if latest_close > current_period_high_5d:
                        is_new_break_5d = True
                        break_types_for_history["5d_break_date"] = latest_date_str
                        high_prices_for_stock_output["5d"] = current_period_high_5d
                    
                    is_continued_break_5d = False
                    if not is_new_break_5d and "5d_break_date" in stock_hist_today:
                        hist_break_date = datetime.strptime(stock_hist_today["5d_break_date"], "%Y-%m-%d").date()
                        days_since = (latest_date_df.date() - hist_break_date).days
                        if 0 <= days_since <= KEEP_5D_BREAK_DAYS:
                            is_continued_break_5d = True
                            break_types_for_history["5d_break_date"] = stock_hist_today["5d_break_date"]
                            break_types_for_history["5d_days_since"] = days_since
                            high_prices_for_stock_output["5d"] = stock_hist_today.get("high_prices",{}).get("5d", current_period_high_5d)
                    
                    if is_new_break_5d or is_continued_break_5d:
                        broke_high = True
                        reason = "5 Days High (New Break)" if is_new_break_5d else f"5 Days High (Day {break_types_for_history.get('5d_days_since',0)} of {KEEP_5D_BREAK_DAYS})"
                        break_reasons.append(reason)

                # 1-month high
                if options["1_month"] and len(df) >= 22:
                    is_new_break_1m = False
                    current_period_high_1m = df["high"].iloc[-22:-1].max()
                    if latest_close > current_period_high_1m:
                        is_new_break_1m = True
                        break_types_for_history["1m_break_date"] = latest_date_str
                        high_prices_for_stock_output["1m"] = current_period_high_1m

                    is_continued_break_1m = False
                    if not is_new_break_1m and "1m_break_date" in stock_hist_today:
                        hist_break_date = datetime.strptime(stock_hist_today["1m_break_date"], "%Y-%m-%d").date()
                        days_since = (latest_date_df.date() - hist_break_date).days
                        if 0 <= days_since <= KEEP_1M_BREAK_DAYS:
                            is_continued_break_1m = True
                            break_types_for_history["1m_break_date"] = stock_hist_today["1m_break_date"]
                            break_types_for_history["1m_days_since"] = days_since
                            high_prices_for_stock_output["1m"] = stock_hist_today.get("high_prices",{}).get("1m", current_period_high_1m)

                    if is_new_break_1m or is_continued_break_1m:
                        broke_high = True
                        reason = "1 Month High (New Break)" if is_new_break_1m else f"1 Month High (Day {break_types_for_history.get('1m_days_since',0)} of {KEEP_1M_BREAK_DAYS})"
                        break_reasons.append(reason)
                
                # 2-months high
                if options["2_months"] and len(df) >= 44:
                    is_new_break_2m = False
                    current_period_high_2m = df["high"].iloc[-44:-1].max()
                    if latest_close > current_period_high_2m:
                        is_new_break_2m = True
                        break_types_for_history["2m_break_date"] = latest_date_str
                        high_prices_for_stock_output["2m"] = current_period_high_2m
                    
                    is_continued_break_2m = False
                    if not is_new_break_2m and "2m_break_date" in stock_hist_today:
                        hist_break_date = datetime.strptime(stock_hist_today["2m_break_date"], "%Y-%m-%d").date()
                        days_since = (latest_date_df.date() - hist_break_date).days
                        if 0 <= days_since <= KEEP_2M_BREAK_DAYS:
                            is_continued_break_2m = True
                            break_types_for_history["2m_break_date"] = stock_hist_today["2m_break_date"]
                            break_types_for_history["2m_days_since"] = days_since
                            high_prices_for_stock_output["2m"] = stock_hist_today.get("high_prices",{}).get("2m", current_period_high_2m)

                    if is_new_break_2m or is_continued_break_2m:
                        broke_high = True
                        reason = "2 Months High (New Break)" if is_new_break_2m else f"2 Months High (Day {break_types_for_history.get('2m_days_since',0)} of {KEEP_2M_BREAK_DAYS})"
                        break_reasons.append(reason)

                # 3-months high
                if options["3_months"] and len(df) >= 66:
                    is_new_break_3m = False
                    current_period_high_3m = df["high"].iloc[-66:-1].max()
                    if latest_close > current_period_high_3m:
                        is_new_break_3m = True
                        break_types_for_history["3m_break_date"] = latest_date_str
                        high_prices_for_stock_output["3m"] = current_period_high_3m

                    is_continued_break_3m = False
                    if not is_new_break_3m and "3m_break_date" in stock_hist_today:
                        hist_break_date = datetime.strptime(stock_hist_today["3m_break_date"], "%Y-%m-%d").date()
                        days_since = (latest_date_df.date() - hist_break_date).days
                        if 0 <= days_since <= KEEP_3M_BREAK_DAYS:
                            is_continued_break_3m = True
                            break_types_for_history["3m_break_date"] = stock_hist_today["3m_break_date"]
                            break_types_for_history["3m_days_since"] = days_since
                            high_prices_for_stock_output["3m"] = stock_hist_today.get("high_prices",{}).get("3m", current_period_high_3m)
                    
                    if is_new_break_3m or is_continued_break_3m:
                        broke_high = True
                        reason = "3 Months High (New Break)" if is_new_break_3m else f"3 Months High (Day {break_types_for_history.get('3m_days_since',0)} of {KEEP_3M_BREAK_DAYS})"
                        break_reasons.append(reason)
                
                if broke_high:
                    return stock, (break_reasons, latest_close, high_prices_for_stock_output, break_types_for_history), None # No error
                else:
                    return stock, None, f"No breaks for {stock}."

            elif isinstance(data, dict) and data.get("message") == "No data found":
                 return stock, None, f"No data found for {stock} via API."
            else:
                return stock, None, f"Unexpected data structure for {stock}."
        else:
            return stock, None, f"API error for {stock}: {response.status_code} {response.text}"
        
    except requests.exceptions.Timeout:
        return stock, None, f"Request timed out for {stock}."
    except Exception as e:
        return stock, None, f"Error processing {stock}: {str(e)}"

def detect_break_high_price(options, output_list_for_plan, progress_callback, completion_callback, set_continue_button_state_callback):
    """Detect break high price based on selected options and update UI via callbacks. Uses threading for speed."""
    base_url = "https://yfinance-web-indonesia-data.vercel.app"
    
    os.makedirs(DATA_DIR, exist_ok=True)
    stocks = get_stock_list()
    
    output_list_for_plan.clear()
    set_continue_button_state_callback(False)
    
    if not any(options.values()):
        progress_callback("Please select at least one period option.\n")
        completion_callback([], "Please select at least one period option.\n", "")
        return
    
    progress_callback("Starting detection (using threads)...\n")
    if not stocks:
        message = "Stock list is empty. Please check stocks.txt.\n"
        progress_callback(message)
        completion_callback([], message, "Detection aborted.")
        return
        
    progress_callback(f"Total stocks to check: {len(stocks)}\n")
    
    detection_history = load_detection_history()
    current_date_str = datetime.now().strftime("%Y-%m-%d")
    latest_date_for_run_dt = datetime.now().date() # For comparing days_since uniformly
    
    if current_date_str not in detection_history:
        detection_history[current_date_str] = {}
        
    # Prune old history (more than 10 days)
    # This should ideally be based on the actual dates, not just number of keys if keys aren't guaranteed daily
    sorted_history_dates = sorted(list(detection_history.keys()))
    if len(sorted_history_dates) > 10:
        for old_date_key in sorted_history_dates[:-10]: # Keep the 10 most recent keys
            if old_date_key in detection_history:
                del detection_history[old_date_key]
    
    detected_stocks_for_processing = [] 
    processed_count = 0
    total_stocks = len(stocks)

    # Using ThreadPoolExecutor for concurrent requests
    # Max workers can be tuned. Too many might overwhelm the API or local resources.
    # Let's start with a reasonable number, e.g., 5 or 10.
    MAX_WORKERS = 10 
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Map of future to stock symbol for tracking
        future_to_stock = {executor.submit(fetch_and_process_stock_data, 
                                          stock, 
                                          options, 
                                          base_url, 
                                          detection_history.get(current_date_str, {}), # Pass today's history for that stock
                                          latest_date_for_run_dt):
                           stock for stock in stocks}
        
        for future in concurrent.futures.as_completed(future_to_stock):
            stock_symbol = future_to_stock[future]
            try:
                stock_symbol_result, result_data, error_message = future.result()
                
                processed_count += 1
                progress_callback(f"({processed_count}/{total_stocks}) Processed {stock_symbol_result}. ") 

                if error_message:
                    progress_callback(f"Skipped: {error_message}\n")
                
                if result_data: # (break_reasons, latest_close, high_prices_for_stock_output, break_types_for_history)
                    break_reasons, latest_close, high_prices_output, break_types_hist = result_data
                    detected_stocks_for_processing.append((stock_symbol_result, break_reasons, latest_close, high_prices_output))
                    
                    progress_callback(f"Detected for {stock_symbol_result}: { ', '.join(break_reasons) }\n")

                    # Update history for this stock for today
                    if stock_symbol_result not in detection_history[current_date_str]:
                        detection_history[current_date_str][stock_symbol_result] = {}
                    
                    # Persist break types (dates, days_since) and associated high prices
                    for key, value in break_types_hist.items():
                         detection_history[current_date_str][stock_symbol_result][key] = value
                    if high_prices_output: 
                        # Ensure high_prices key exists before trying to merge with it
                        if "high_prices" not in detection_history[current_date_str][stock_symbol_result]:
                            detection_history[current_date_str][stock_symbol_result]["high_prices"] = {}
                        detection_history[current_date_str][stock_symbol_result]["high_prices"].update(high_prices_output)
                
            except Exception as exc:
                processed_count += 1 # Still count as processed for progress
                progress_callback(f"({processed_count}/{total_stocks}) Error processing {stock_symbol}: {exc}\n")
    
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