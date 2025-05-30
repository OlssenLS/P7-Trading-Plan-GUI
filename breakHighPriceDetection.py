import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import sys
from technicalIndicators import apply_technical_filters, get_technical_analysis_summary
import asyncio

MAX_WORKERS = 10 # Define at a suitable scope, e.g., module level

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
async def fetch_and_process_stock_data(stock, break_high_criteria, technical_criteria, base_url, current_date_history, latest_date_for_run_dt):
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
                if break_high_criteria.get("1_day") and len(df) >= 2:
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
                if break_high_criteria.get("5_days") and len(df) >= 6:
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
                if break_high_criteria.get("1_month") and len(df) >= 22:
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
                if break_high_criteria.get("2_months") and len(df) >= 44:
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
                if break_high_criteria.get("3_months") and len(df) >= 66:
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
                    passed_technical_filters = True
                    tech_summary_for_output = "No TA requested."

                    if any(tc_val for tc_key, tc_val in technical_criteria.items() if tc_key != 'use_custom_ema'): # Check if any actual filter is selected
                        # Only run if 'use_custom_ema' is true OR other technical filters are selected.
                        # If 'use_custom_ema' is true but no periods are set, apply_technical_filters should handle it gracefully.
                        run_tech_filters = False
                        if technical_criteria.get('use_custom_ema'):
                            if technical_criteria.get('ema1_period') and technical_criteria.get('ema2_period'):
                                run_tech_filters = True
                        # Check if any other non-EMA technical filter is selected
                        if any(val for key, val in technical_criteria.items() if key not in ['use_custom_ema', 'ema1_period', 'ema2_period'] and val):
                            run_tech_filters = True
                        
                        if run_tech_filters:
                            technical_filter_results = await apply_technical_filters(df, technical_criteria)
                            passed_technical_filters = technical_filter_results["passed_all_selected_technical_filters"]
                            if passed_technical_filters:
                                break_reasons.extend(technical_filter_results["passed_filters_reasons"])
                                tech_summary_for_output = await get_technical_analysis_summary(df, technical_criteria)
                            else:
                                # Failed technical filters after breaking high
                                return stock, None, f"{stock} broke high but failed technical filters: {', '.join(technical_filter_results['failed_filters_details'])}"
                        elif technical_criteria.get('use_custom_ema'): # use_custom_ema was true, but periods might be missing
                            # This implies user wanted custom EMAs but didn't set them properly.
                            # FilterManager modal should prevent this, but as a safeguard:
                            return stock, None, f"{stock} broke high; Custom EMA selected but periods not properly set."

                    if passed_technical_filters:
                        return stock, (break_reasons, latest_close, latest_low_of_day, latest_high_of_day, high_prices_for_stock_output, break_types_for_history, potential_tp_levels_from_history, tech_summary_for_output), None

                else: # Not broke_high
                    tech_summary_for_no_break_message = "No TA requested or no break." # Default message

                    # Prepare criteria for TA summary of non-breaking stocks.
                    # Standard EMAs (if selected and not in advanced mode) and other indicators (MACD, Stoch, Vol)
                    # should be summarized, but custom EMAs should not be part of this specific summary.
                    
                    # Check if any non-custom-EMA technical criteria were originally selected by the user.
                    # technical_criteria holds the original user selections.
                    should_generate_non_custom_ema_summary = False
                    # Check if standard EMAs were selected (this implies not using custom EMAs for this check)
                    if not technical_criteria.get("use_custom_ema", False): # If not in user-selected custom EMA mode
                        if technical_criteria.get('ema_20') or technical_criteria.get('ema_60'):
                            should_generate_non_custom_ema_summary = True
                    # Check for other general indicators
                    if any(val for key, val in technical_criteria.items() if key in ['macd', 'stochastic', 'volume'] and val):
                        should_generate_non_custom_ema_summary = True
                    
                    if should_generate_non_custom_ema_summary:
                        # Create a temporary criteria copy that explicitly disables the custom EMA part 
                        # for the get_technical_analysis_summary call.
                        criteria_for_no_break_summary_display = technical_criteria.copy()
                        criteria_for_no_break_summary_display['use_custom_ema'] = False 
                        # Remove period keys as well, for clarity, though get_technical_analysis_summary
                        # primarily gates on 'use_custom_ema'.
                        criteria_for_no_break_summary_display.pop('ema1_period', None)
                        criteria_for_no_break_summary_display.pop('ema2_period', None)
                        
                        tech_summary_for_no_break_message = await get_technical_analysis_summary(df, criteria_for_no_break_summary_display)
                    
                    return stock, None, f"No break high criteria met for {stock}. TA: {tech_summary_for_no_break_message}"

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
async def fetch_and_process_stock_data_wrapper(stock, break_high_criteria, technical_criteria, base_url, current_date_history, latest_date_for_run_dt):
    # This wrapper is needed if fetch_and_process_stock_data is async and called from a sync context via executor
    return await fetch_and_process_stock_data(stock, break_high_criteria, technical_criteria, base_url, current_date_history, latest_date_for_run_dt)

def run_async_task_in_thread(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(coro)
    finally:
        loop.close()
    return result

def detect_break_high_price(filters, output_list_for_plan, progress_callback, post_detection_callback, set_plan_type_callback, trend_line_confirmation_enabled):
    progress_callback("Starting stock detection process...")
    stock_list = get_stock_list()
    if not stock_list:
        progress_callback("Stock list is empty. Please check stocks.txt.")
        post_detection_callback([], "Stock list empty.", "", False)
        return

    base_url = "https://yfinance-web-indonesia-data.vercel.app" # Consider making this configurable
    
    break_high_criteria = filters.get("break_high", {})
    technical_criteria = filters.get("technical", {})

    current_date_history = load_detection_history()
    latest_date_for_run = datetime.now().strftime("%Y-%m-%d")

    new_history_for_current_run = {}
    detected_stocks_summary_data = [] 
    total_stocks = len(stock_list)
    processed_count = 0

    # Determine plan type and if selection should be disabled
    # Default to Swing Trader, enabled selection
    plan_type_for_plan_window = "Swing Trader"
    disable_plan_type_selection = False

    # Example logic: If only 1-day break is selected, suggest Day Trader and disable choice.
    active_break_filters = [k for k, v in break_high_criteria.items() if v]
    if len(active_break_filters) == 1 and active_break_filters[0] == "1_day":
        plan_type_for_plan_window = "Day Trader"
        disable_plan_type_selection = True
        progress_callback("Note: Only 1-day break selected. Plan type will be set to Day Trader.")
    
    set_plan_type_callback(plan_type_for_plan_window, disable_plan_type_selection)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_stock = {}
        for stock_name in stock_list:
            # Pass technical_criteria which now includes custom EMA info if set
            coro = fetch_and_process_stock_data_wrapper(
                stock_name, 
                break_high_criteria, 
                technical_criteria, 
                base_url, 
                current_date_history.get(latest_date_for_run, {}), # Pass history for today for this stock
                latest_date_for_run
            )
            future_to_stock[executor.submit(run_async_task_in_thread, coro)] = stock_name

        for future in concurrent.futures.as_completed(future_to_stock):
            stock_name_completed = future_to_stock[future]
            processed_count += 1
            progress_callback(f"Processing {stock_name_completed} ({processed_count}/{total_stocks})...")
            try:
                stock_symbol, result_data, error_message = future.result()
                
                if error_message:
                    progress_callback(f"Skipped {stock_symbol}: {error_message}")
                elif result_data:
                    # result_data is (break_reasons, latest_close, latest_low, latest_high, high_prices_output, break_types_hist, potential_tp_levels, tech_summary)
                    break_reasons_list, latest_close_val, latest_low_val, latest_high_val, high_prices_dict, break_types_dict, potential_tps_list, tech_summary_str = result_data
                    
                    progress_callback(f"Detected {stock_symbol}: Reasons - {', '.join(break_reasons_list)}. Tech Summary: {tech_summary_str}")
                    
                    # Store data for plan generation
                    stock_data_for_plan = [
                        stock_symbol, 
                        latest_close_val, 
                        latest_low_val, 
                        latest_high_val, 
                        break_reasons_list, 
                        high_prices_dict, # Pass the dictionary of high prices
                        potential_tps_list, # Pass potential TPs
                        tech_summary_str # Pass tech summary
                    ]
                    output_list_for_plan.append(stock_data_for_plan) # This list is shared and used by the caller
                    detected_stocks_summary_data.append(stock_data_for_plan)

                    # Update history for this stock for the current run date
                    if latest_date_for_run not in new_history_for_current_run:
                        new_history_for_current_run[latest_date_for_run] = {}
                    
                    # Ensure high_prices_dict is stored under a 'high_prices' key if that's how it's expected later
                    new_history_for_current_run[latest_date_for_run][stock_symbol] = {
                        **break_types_dict, # This contains { "1d_break_date": "YYYY-MM-DD", "1d_days_since": X, ... }
                        "high_prices": high_prices_dict # e.g., { "1d": 100, "5d": 95 }
                    }

            except Exception as exc:
                progress_callback(f"Error processing {stock_name_completed}: {exc}")

    # After all stocks are processed, update the main detection history file
    # Merge new_history_for_current_run into current_date_history (which was loaded at start)
    # This ensures we don't overwrite history for other dates or other stocks on the same date if run multiple times
    for date_key, stocks_on_date in new_history_for_current_run.items():
        if date_key not in current_date_history:
            current_date_history[date_key] = {}
        for stock_key, stock_data_hist in stocks_on_date.items():
            current_date_history[date_key][stock_key] = stock_data_hist
            
    save_detection_history(current_date_history)

    summary_text = f"Detection complete. Found {len(detected_stocks_summary_data)} potential stock(s) based on criteria.\n"
    for data in detected_stocks_summary_data:
        summary_text += f"- {data[0]}: {', '.join(data[4])}\n" # Removed Tech: {data[7]}

    final_status_message = "Ready to proceed to plan setup if stocks were detected." if detected_stocks_summary_data else "No stocks met the criteria."
    
    # Call the post_detection_callback which might open the trend line confirmation window or directly update UI
    post_detection_callback(detected_stocks_summary_data, summary_text, final_status_message, trend_line_confirmation_enabled and bool(detected_stocks_summary_data)) 