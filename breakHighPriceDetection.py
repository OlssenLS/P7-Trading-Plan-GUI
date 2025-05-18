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
                # DEBUG: Log API response details
                print(f"[DEBUG] {stock}: API returned {len(data['historical_data'])} data points")
                
                # Check the earliest and latest dates in the API response
                try:
                    dates = [item.get('date') for item in data['historical_data'] if 'date' in item]
                    if dates:
                        earliest_date = min(dates)
                        latest_date = max(dates)
                        print(f"[DEBUG] {stock}: Date range in API data: {earliest_date} to {latest_date}")
                    # Log a sample data point to verify structure
                    if data['historical_data']:
                        sample_point = data['historical_data'][0]
                        print(f"[DEBUG] {stock}: Sample data structure: {sample_point}")
                except Exception as e:
                    print(f"[DEBUG] {stock}: Error parsing API dates: {e}")
                
                df = pd.DataFrame(data["historical_data"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                
                if df.empty:
                    # progress_callback(f"  No historical data rows for {stock} after processing.\n")
                    return stock, None, f"No historical data for {stock}."

                latest_close = df.iloc[-1]["close"]
                latest_high_of_day = df.iloc[-1]["high"]
                latest_low_of_day = df.iloc[-1]["low"]
                latest_date_df = df.iloc[-1]["date"]
                latest_date_str = latest_date_df.strftime("%Y-%m-%d")

                # Find potential TP levels from historical highs > latest_high_of_day
                potential_tp_levels_from_history = []
                if not df.empty and len(df) > 1: # Ensure there's historical data to check against
                    # Exclude the most recent day's high since TPs should be above it.
                    # We consider all highs from days *before* the latest_date_df.
                    historical_data_for_tp_search = df[df["date"] < latest_date_df]
                    
                    # DEBUG: Log historical data stats
                    print(f"[DEBUG] {stock}: Total historical days: {len(df)}, Days before latest: {len(historical_data_for_tp_search)}")
                    print(f"[DEBUG] {stock}: Latest high: {latest_high_of_day:.2f}, Latest date: {latest_date_str}")
                    
                    if not historical_data_for_tp_search.empty:
                        historical_highs_values = historical_data_for_tp_search["high"]
                        higher_historical_highs = historical_highs_values[historical_highs_values > latest_high_of_day]
                        
                        # DEBUG: Log higher highs found
                        higher_count = len(higher_historical_highs) if not higher_historical_highs.empty else 0
                        print(f"[DEBUG] {stock}: Found {higher_count} historical highs > {latest_high_of_day:.2f}")
                        
                        if not higher_historical_highs.empty:
                            potential_tp_levels_from_history = sorted(list(set(higher_historical_highs.tolist())))
                            
                            # DEBUG: Log actual values
                            print(f"[DEBUG] {stock}: Sorted unique higher highs: {[f'{h:.2f}' for h in potential_tp_levels_from_history]}")
                        else:
                            print(f"[DEBUG] {stock}: No higher historical highs found")
                    else:
                        print(f"[DEBUG] {stock}: No historical data before latest date")
                else:
                    print(f"[DEBUG] {stock}: Insufficient historical data for TP search")
                
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
                    # Return: stock, (break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_for_stock_output, break_types_for_history, potential_tp_levels_from_history), error_message
                    return stock, (break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_for_stock_output, break_types_for_history, potential_tp_levels_from_history), None
                else:
                    # For consistency, return the full tuple structure even if no break, with empty break_reasons and high_prices_for_stock_output
                    return stock, ([], latest_close, latest_low_of_day, latest_high_of_day, {}, break_types_for_history, potential_tp_levels_from_history), f"No breaks for {stock}."

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
                    # Even if skipped due to "No breaks", result_data might contain latest prices and potential_tp_levels
                    # If we wanted to use that, we could, but for now, we only add to detected_stocks_for_processing if there was an actual break.
                
                # We now only proceed to add to detected_stocks_for_processing if there are actual break_reasons.
                # The result_data from fetch_and_process_stock_data always has the full tuple structure.
                if result_data:
                    break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_output, break_types_hist, potential_tp_levels = result_data
                    
                    if break_reasons: # Only proceed if actual break reasons exist
                        # Append tuple: (stock_name, reasons, latest_close, latest_low_of_day, latest_high_of_day, period_high_prices_info, potential_tp_levels_from_history)
                        detected_stocks_for_processing.append((stock_symbol_result, break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_output, potential_tp_levels))
                        progress_callback(f"Detected for {stock_symbol_result}: { ', '.join(break_reasons) }\n")

                        # Update history for this stock for today (only if it was a break)
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
        for stock_name, reasons, close, low_of_day, high_of_day, highs_info, pot_tps in detected_stocks_for_processing:
            summary_text_parts.append(f"{stock_name}: { ', '.join(reasons) } - Close: {close:.2f}, Low: {low_of_day:.2f}, High: {high_of_day:.2f}\n")
            if highs_info: # This is period_high_prices_info (highs that were broken)
                summary_text_parts.append(f"    Broken Period Highs: { {k: f'{v:.2f}' for k, v in highs_info.items()} }\n")
            if pot_tps:
                summary_text_parts.append(f"    Potential TPs from History (> {high_of_day:.2f}): { [f'{tp:.2f}' for tp in pot_tps[:3]] }\n") # Show first 3
            summary_text_parts.append("\n") # Add a newline for better readability per stock
    else:
        summary_text_parts.append("No stocks breaking high price detected.\n")
    
    final_status_message = f"\nDetection complete. Found {len(detected_stocks_for_processing)} stocks breaking high price.\n"
    
    completion_callback(detected_stocks_for_processing, "".join(summary_text_parts), final_status_message)

    if detected_stocks_for_processing:
        set_continue_button_state_callback(True)
    # No explicit else to disable button, it's handled by the initial set_continue_button_state_callback(False)
    # and only enabled if stocks are found. 