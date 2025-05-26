import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import sys
from technicalIndicators import apply_technical_filters, get_technical_analysis_summary

# --- Path Helpers (Resource and Persistent Data) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_application_path():
    """Returns the base application path."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_persistent_data_path(relative_path):
    """ Get absolute path for persistent data storage. """
    base_path = get_application_path()
    return os.path.join(base_path, relative_path)

STOCKS_FILE = resource_path("stocks.txt")
DATA_DIR = get_persistent_data_path("data")

DETECTION_HISTORY_FILE = os.path.join(DATA_DIR, "detection_history.json")
KEEP_1D_BREAK_DAYS = 1
KEEP_5D_BREAK_DAYS = 3
KEEP_1M_BREAK_DAYS = 5
KEEP_2M_BREAK_DAYS = 6
KEEP_3M_BREAK_DAYS = 7

# --- Stock List and Detection History Management ---
def get_stock_list():
    """Read stock list from stocks.txt or use default if not found."""
    stock_list = []
    default_stocks_list = [
        "BBCA", "BBRI", "BMRI", "TLKM", "ASII",
        "UNVR", "INDF", "ICBP", "SMGR", "CPIN"
    ]

    try:
        os.makedirs(DATA_DIR, exist_ok=True)

        if os.path.exists(STOCKS_FILE):
            with open(STOCKS_FILE, "r") as f:
                stock_list = [line.strip() for line in f.readlines() if line.strip()]
            if not stock_list:
                print(f"Warning: {STOCKS_FILE} was found but is empty. Using default stock list.")
                stock_list = default_stocks_list
        else:
            print(f"Warning: {STOCKS_FILE} not found. Using default stock list. Ensure it is added via PyInstaller's --add-data.")
            stock_list = default_stocks_list
            
    except Exception as e:
        print(f"Error reading {STOCKS_FILE}: {e}. Using default stock list.")
        stock_list = default_stocks_list
    return stock_list

def load_detection_history():
    """Load detection history from file if it exists"""
    history = {}
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(DETECTION_HISTORY_FILE):
            with open(DETECTION_HISTORY_FILE, "r") as f:
                history = json.load(f)
    except Exception as e:
        print(f"Error loading detection history: {e}")
    return history

def save_detection_history(history):
    """Save detection history to file"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(DETECTION_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"Error saving detection history: {e}")

# --- Core Stock Data Fetching and Processing ---
def fetch_and_process_stock_data(stock, options, base_url, current_date_history, latest_date_for_run_dt):
    """Fetches and processes data for a single stock. Designed to be run in a thread."""
    try:
        endpoint_url = f"{base_url}/api/stocks/{stock}?start_date=2023-01-01"
        
        response = requests.get(endpoint_url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "historical_data" in data and data["historical_data"] and len(data["historical_data"]) > 0:
                df = pd.DataFrame(data["historical_data"])
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                
                if df.empty:
                    return stock, None, f"No historical data for {stock}."

                latest_close = df.iloc[-1]["close"]
                latest_high_of_day = df.iloc[-1]["high"]
                latest_low_of_day = df.iloc[-1]["low"]
                latest_date_df = df.iloc[-1]["date"]
                latest_date_str = latest_date_df.strftime("%Y-%m-%d")

                potential_tp_levels_from_history = []
                if not df.empty and len(df) > 1:
                    historical_data_for_tp_search = df[df["date"] < latest_date_df]
                    
                    if not historical_data_for_tp_search.empty:
                        historical_highs_values = historical_data_for_tp_search["high"]
                        higher_historical_highs = historical_highs_values[historical_highs_values > latest_high_of_day]
                        
                        if not higher_historical_highs.empty:
                            potential_tp_levels_from_history = sorted(list(set(higher_historical_highs.tolist())))
                
                broke_high = False
                break_reasons = []
                break_types_for_history = {}
                high_prices_for_stock_output = {}

                stock_hist_today = current_date_history.get(stock, {})

                # Break 1d High (yesterday's high)
                if options["1_day"] and len(df) >= 2:
                    is_new_break_1d = False
                    yesterday_high = df.iloc[-2]["high"]
                    if latest_high_of_day > yesterday_high:
                        is_new_break_1d = True
                        broke_high = True
                        break_types_for_history["1d_break_date"] = latest_date_str
                        high_prices_for_stock_output["1d"] = yesterday_high
                        break_reasons.append("1 Day High (New Break)")
                    elif "1d_break_date" in stock_hist_today:
                        hist_break_date = datetime.strptime(stock_hist_today["1d_break_date"], "%Y-%m-%d").date()
                        days_since = (latest_date_df.date() - hist_break_date).days
                        if 0 <= days_since <= KEEP_1D_BREAK_DAYS:
                            broke_high = True
                            break_types_for_history["1d_break_date"] = stock_hist_today["1d_break_date"]
                            break_types_for_history["1d_days_since"] = days_since
                            high_prices_for_stock_output["1d"] = stock_hist_today.get("high_prices",{}).get("1d", yesterday_high)
                            break_reasons.append(f"1 Day High (Day {days_since} of {KEEP_1D_BREAK_DAYS})")

                # Break 5-days high
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

                # Break 1-month high
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
                
                # Break 2-months high
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

                # Break 3-months high
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
                    return stock, (break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_for_stock_output, break_types_for_history, potential_tp_levels_from_history), None
                else:
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

# --- Main Detection Function ---
def detect_break_high_price(filters, output_list_for_plan, progress_callback, post_detection_callback, set_plan_type_callback, trend_line_confirmation_enabled):
    """Detect break high price based on selected filters and update UI via callbacks."""
    base_url = "https://yfinance-web-indonesia-data.vercel.app"
    
    os.makedirs(DATA_DIR, exist_ok=True)
    stocks = get_stock_list()
    
    output_list_for_plan.clear()
    
    break_high_options = filters.get('break_high', {})
    technical_options = filters.get('technical', {})
    
    only_1d_break = (break_high_options.get("1_day", False) and 
                    not any(break_high_options.get(option, False) 
                           for option in ["5_days", "1_month", "2_months", "3_months"]))
    
    if only_1d_break:
        set_plan_type_callback("Day Trade", True)
    else:
        set_plan_type_callback("Swing Trader", False)
    
    if not any(break_high_options.values()):
        progress_callback("Please select at least one Break High Price filter.\n")
        post_detection_callback([], "Please select at least one Break High Price filter.\n", "", False)
        return
    
    progress_callback("Starting detection (using threads)...\n")
    if not stocks:
        message = "Stock list is empty. Please check stocks.txt.\n"
        progress_callback(message)
        post_detection_callback([], message, "Detection aborted.", False)
        return
    
    progress_callback(f"Total stocks to check: {len(stocks)}\n")
    
    detection_history = load_detection_history()
    current_date_str = datetime.now().strftime("%Y-%m-%d")
    latest_date_for_run_dt = datetime.now().date()
    
    if current_date_str not in detection_history:
        detection_history[current_date_str] = {}
    
    sorted_history_dates = sorted(list(detection_history.keys()))
    if len(sorted_history_dates) > 10:
        for old_date_key in sorted_history_dates[:-10]:
            if old_date_key in detection_history:
                del detection_history[old_date_key]
    
    detected_stocks_for_processing = []
    processed_count = 0
    total_stocks = len(stocks)

    MAX_WORKERS = 10 
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_stock = {executor.submit(fetch_and_process_stock_data, 
                                           stock, 
                                           {
                                               "1_day": break_high_options.get("1_day", False),
                                               "5_days": break_high_options.get("5_days", False),
                                               "1_month": break_high_options.get("1_month", False),
                                               "2_months": break_high_options.get("2_months", False),
                                               "3_months": break_high_options.get("3_months", False)
                                           }, 
                                           base_url, 
                                           detection_history.get(current_date_str, {}),
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
                    continue

                if result_data:
                    break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_output, break_types_hist, potential_tp_levels = result_data
                    
                    if break_reasons:
                        # Apply technical filters
                        if any(technical_options.values()):
                            try:
                                response = requests.get(f"{base_url}/api/stocks/{stock_symbol_result}?start_date=2023-01-01")
                                if response.status_code == 200:
                                    data = response.json()
                                    if data and "historical_data" in data:
                                        df = pd.DataFrame(data["historical_data"])
                                        df["date"] = pd.to_datetime(df["date"])
                                        df = df.sort_values("date")
                                        
                                        if not apply_technical_filters(df, technical_options):
                                            progress_callback(f"Skipped {stock_symbol_result}: Did not meet technical criteria.\n")
                                            continue
                                        
                                        tech_summary = get_technical_analysis_summary(df, technical_options)
                                        break_reasons.append(f"Technical Analysis: {tech_summary}")
                            except Exception as e:
                                progress_callback(f"Error applying technical filters for {stock_symbol_result}: {str(e)}\n")
                                continue

                        detected_stocks_for_processing.append((stock_symbol_result, break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_output, potential_tp_levels))
                        progress_callback(f"Detected for {stock_symbol_result}: { ', '.join(break_reasons) }\n")

                        if stock_symbol_result not in detection_history[current_date_str]:
                            detection_history[current_date_str][stock_symbol_result] = {}
                        
                        for key, value in break_types_hist.items():
                             detection_history[current_date_str][stock_symbol_result][key] = value
                        if high_prices_output: 
                            if "high_prices" not in detection_history[current_date_str][stock_symbol_result]:
                                detection_history[current_date_str][stock_symbol_result]["high_prices"] = {}
                            detection_history[current_date_str][stock_symbol_result]["high_prices"].update(high_prices_output)
                
            except Exception as exc:
                processed_count += 1
                progress_callback(f"({processed_count}/{total_stocks}) Error processing {stock_symbol}: {exc}\n")

    save_detection_history(detection_history)
    output_list_for_plan.extend(detected_stocks_for_processing)

    summary_text_parts = []
    if detected_stocks_for_processing:
        summary_text_parts.append("Detected stocks breaking high price and meeting technical criteria:\n\n")
        for stock_name, reasons, close, low_of_day, high_of_day, highs_info, pot_tps in detected_stocks_for_processing:
            summary_text_parts.append(f"{stock_name}: { ', '.join(reasons) } - Close: {close:.2f}, Low: {low_of_day:.2f}, High: {high_of_day:.2f}\n")
            if highs_info:
                summary_text_parts.append(f"    Broken Period Highs: { {k: f'{v:.2f}' for k, v in highs_info.items()} }\n")
            if pot_tps:
                summary_text_parts.append(f"    Potential TPs from History (> {high_of_day:.2f}): { [f'{tp:.2f}' for tp in pot_tps[:3]] }\n")
            summary_text_parts.append("\n")
    else:
        summary_text_parts.append("No stocks meeting all selected criteria.\n")
    
    final_status_message = f"\nDetection complete. Found {len(detected_stocks_for_processing)} stocks meeting all criteria.\n"
    
    if trend_line_confirmation_enabled and detected_stocks_for_processing:
        progress_callback("Trend line confirmation step required. Stocks will be shown for manual review.\n")
        post_detection_callback(detected_stocks_for_processing, "".join(summary_text_parts), final_status_message, True)

    else:
        post_detection_callback(detected_stocks_for_processing, "".join(summary_text_parts), final_status_message, False) 