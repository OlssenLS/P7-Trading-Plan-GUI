import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import requests
import os
import pandas as pd
from datetime import datetime, timedelta
import json

# Get the script directory for file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

root = ttk.Window(themename="darkly")
root.title("Trading Plan Generator")
root.geometry("800x600")
root.resizable(True, True)

center_frame = ttk.Frame(root)
center_frame.pack(expand=True, fill=BOTH)
center_frame.place(relx=0.5, rely=0.5, anchor=CENTER)

# --- API check ---
api_status_label = ttk.Label(center_frame, text="Checking API availability...")
api_status_label.grid(column=0, row=1, padx=10, pady=10)
spinner = ttk.Progressbar(center_frame, orient=HORIZONTAL, length=300)
spinner.grid(column=0, row=0, padx=10, pady=10)
spinner.start()

# Constants for break tracking
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
STOCKS_FILE = os.path.join(SCRIPT_DIR, "stocks.txt")
DETECTION_HISTORY_FILE = os.path.join(DATA_DIR, "detection_history.json")
KEEP_5D_BREAK_DAYS = 3
KEEP_1M_BREAK_DAYS = 5
KEEP_3M_BREAK_DAYS = 7

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# Create default stocks.txt if it doesn't exist
if not os.path.exists(STOCKS_FILE):
    default_stocks = [
        "BBCA", "BBRI", "BMRI", "TLKM", "ASII", 
        "UNVR", "INDF", "ICBP", "SMGR", "CPIN"
    ]
    with open(STOCKS_FILE, "w") as f:
        f.write("\n".join(default_stocks))

def get_stock_list():
    """Read stock list from stocks.txt"""
    stock_list = []
    try:
        with open(STOCKS_FILE, "r") as f:
            stock_list = [line.strip() for line in f.readlines() if line.strip()]
    except Exception as e:
        print(f"Error reading stocks.txt: {e}")
    return stock_list

def load_detection_history():
    """Load detection history from file if it exists"""
    history = {}
    try:
        if os.path.exists(DETECTION_HISTORY_FILE):
            with open(DETECTION_HISTORY_FILE, "r") as f:
                history = json.load(f)
    except Exception as e:
        print(f"Error loading detection history: {e}")
    return history

def save_detection_history(history):
    """Save detection history to file"""
    try:
        with open(DETECTION_HISTORY_FILE, "w") as f:
            json.dump(history, f)
    except Exception as e:
        print(f"Error saving detection history: {e}")

def detect_break_high_price(options, result_text):
    """Detect break high price based on selected options"""
    base_url = "https://yfinance-web-indonesia-data.vercel.app"
    stocks = get_stock_list()
    
    # Check if at least one option is selected
    if not any(options.values()):
        result_text.insert(END, "Please select at least one period option.\n")
        return
    
    # Clear result text
    result_text.delete(1.0, END)
    
    result_text.insert(END, "Starting detection...\n")
    result_text.see(END)
    
    # Debug total stocks
    result_text.insert(END, f"Total stocks to check: {len(stocks)}\n")
    result_text.see(END)
    
    # Load detection history
    detection_history = load_detection_history()
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Create new empty history for today if it doesn't exist
    if current_date not in detection_history:
        detection_history[current_date] = {}
        
    # Clean up old dates (keep only last 10 days)
    dates = sorted(list(detection_history.keys()))
    if len(dates) > 10:
        for old_date in dates[:-10]:
            if old_date in detection_history:
                del detection_history[old_date]
    
    detected_stocks = []
    
    # Process each stock
    for stock in stocks:
        try:
            endpoint_url = f"{base_url}/api/stocks/{stock}?start_date=2023-01-01"
            result_text.insert(END, f"Checking {stock}...\n")
            result_text.see(END)
            
            response = requests.get(endpoint_url)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "historical_data" in data and len(data["historical_data"]) > 0:
                    result_text.insert(END, f"  Got data for {stock} ({len(data['historical_data'])} records)\n")
                    result_text.see(END)
                    
                    df = pd.DataFrame(data["historical_data"])
                    
                    # Convert date to datetime
                    df["date"] = pd.to_datetime(df["date"])
                    
                    # Sort by date
                    df = df.sort_values("date")
                    
                    # Get latest close price and date
                    latest_close = df.iloc[-1]["close"]
                    latest_date = df.iloc[-1]["date"]
                    latest_date_str = latest_date.strftime("%Y-%m-%d")
                    
                    # Debug message for each stock
                    debug_message = f"\n{stock} - Latest close: {latest_close:.2f} on {latest_date_str}\n"
                    result_text.insert(END, debug_message)
                    result_text.see(END)
                    
                    # Get dates for checking recent breaks
                    available_dates = sorted(df["date"].unique())
                    
                    # Track if this stock broke high in any period
                    broke_high = False
                    break_reasons = []
                    break_types = {}
                    
                    # Debug values for high prices
                    five_days_high = None
                    one_month_high = None
                    three_months_high = None
                    
                    # Check for 5-day high price break
                    if options["5_days"] and len(df) >= 6:
                        # Get the latest break status
                        break_5d = False
                        
                        # Use last n periods rather than calendar days
                        date_list = sorted(df["date"].unique())
                        if len(date_list) >= 6:
                            # Get dates excluding the latest date
                            prev_dates = date_list[:-1]
                            # Get the last 5 dates
                            last_5_dates = prev_dates[-5:]
                            
                            five_days_df = df[df["date"].isin(last_5_dates)]
                            
                            if not five_days_df.empty:
                                five_days_high = five_days_df["high"].max()
                                debug_message = f"  5-day high: {five_days_high:.2f}, Latest close: {latest_close:.2f}, Break: {latest_close > five_days_high}\n"
                                result_text.insert(END, debug_message)
                                result_text.see(END)
                                
                                if latest_close > five_days_high:
                                    # Found a new break
                                    break_5d = True
                                    # Record the break date
                                    break_types["5d_break_date"] = latest_date_str
                            else:
                                result_text.insert(END, f"  5-day data empty (unusual)\n")
                                result_text.see(END)
                        else:
                            result_text.insert(END, f"  Not enough data points for 5-day analysis\n")
                            result_text.see(END)
                        
                        # Check if there's a recent break that's still valid (within KEEP_5D_BREAK_DAYS)
                        if not break_5d and stock in detection_history.get(current_date, {}):
                            stock_history = detection_history[current_date].get(stock, {})
                            if "5d_break_date" in stock_history:
                                break_date = datetime.strptime(stock_history["5d_break_date"], "%Y-%m-%d")
                                recent_dates = [d for d in available_dates if d <= latest_date]
                                if len(recent_dates) >= 2:  # Need at least 2 dates to calculate days since break
                                    # Find position of break date in available dates
                                    if break_date in recent_dates:
                                        break_idx = recent_dates.index(break_date)
                                        days_since_break = len(recent_dates) - break_idx - 1
                                        if days_since_break <= KEEP_5D_BREAK_DAYS:
                                            break_5d = True
                                            break_types["5d_break_date"] = stock_history["5d_break_date"]
                                            break_types["5d_days_since"] = days_since_break
                        
                        if break_5d:
                            broke_high = True
                            if "5d_days_since" in break_types:
                                break_reasons.append(f"5 Days High (Day {break_types['5d_days_since']} of {KEEP_5D_BREAK_DAYS})")
                            else:
                                break_reasons.append("5 Days High (New Break)")
                    
                    # Check for 1-month high price break
                    if options["1_month"] and len(df) >= 22:  # ~22 trading days in a month
                        # Get the latest break status
                        break_1m = False
                        
                        # Check for new break - FIX: use last n periods rather than calendar days
                        date_list = sorted(df["date"].unique())
                        if len(date_list) >= 23:  # 22 days + current
                            # Get dates excluding the latest date
                            prev_dates = date_list[:-1]
                            # Get the last 22 dates (approx 1 month of trading)
                            last_22_dates = prev_dates[-22:]
                            
                            one_month_df = df[df["date"].isin(last_22_dates)]
                            
                            if not one_month_df.empty:
                                one_month_high = one_month_df["high"].max()
                                debug_message = f"  1-month high: {one_month_high:.2f}, Latest close: {latest_close:.2f}, Break: {latest_close > one_month_high}\n"
                                result_text.insert(END, debug_message)
                                result_text.see(END)
                                
                                if latest_close > one_month_high:
                                    # Found a new break
                                    break_1m = True
                                    # Record the break date
                                    break_types["1m_break_date"] = latest_date_str
                            else:
                                result_text.insert(END, f"  1-month data empty (unusual)\n")
                                result_text.see(END)
                        else:
                            result_text.insert(END, f"  Not enough data points for 1-month analysis\n")
                            result_text.see(END)
                        
                        # Check if there's a recent break that's still valid (within KEEP_1M_BREAK_DAYS)
                        if not break_1m and stock in detection_history.get(current_date, {}):
                            stock_history = detection_history[current_date].get(stock, {})
                            if "1m_break_date" in stock_history:
                                break_date = datetime.strptime(stock_history["1m_break_date"], "%Y-%m-%d")
                                recent_dates = [d for d in available_dates if d <= latest_date]
                                if len(recent_dates) >= 2:  # Need at least 2 dates to calculate days since break
                                    # Find position of break date in available dates
                                    if break_date in recent_dates:
                                        break_idx = recent_dates.index(break_date)
                                        days_since_break = len(recent_dates) - break_idx - 1
                                        if days_since_break <= KEEP_1M_BREAK_DAYS:
                                            break_1m = True
                                            break_types["1m_break_date"] = stock_history["1m_break_date"]
                                            break_types["1m_days_since"] = days_since_break
                        
                        if break_1m:
                            broke_high = True
                            if "1m_days_since" in break_types:
                                break_reasons.append(f"1 Month High (Day {break_types['1m_days_since']} of {KEEP_1M_BREAK_DAYS})")
                            else:
                                break_reasons.append("1 Month High (New Break)")
                    
                    # Check for 3-months high price break
                    if options["3_months"] and len(df) >= 66:  # ~66 trading days in 3 months
                        # Get the latest break status
                        break_3m = False
                        
                        # Check for new break - FIX: use last n periods rather than calendar days
                        date_list = sorted(df["date"].unique())
                        if len(date_list) >= 67:  # 66 days + current
                            # Get dates excluding the latest date
                            prev_dates = date_list[:-1]
                            # Get the last 66 dates (approx 3 months of trading)
                            last_66_dates = prev_dates[-66:]
                            
                            three_months_df = df[df["date"].isin(last_66_dates)]
                            
                            if not three_months_df.empty:
                                three_months_high = three_months_df["high"].max()
                                debug_message = f"  3-month high: {three_months_high:.2f}, Latest close: {latest_close:.2f}, Break: {latest_close > three_months_high}\n"
                                result_text.insert(END, debug_message)
                                result_text.see(END)
                                
                                if latest_close > three_months_high:
                                    # Found a new break
                                    break_3m = True
                                    # Record the break date
                                    break_types["3m_break_date"] = latest_date_str
                            else:
                                result_text.insert(END, f"  3-month data empty (unusual)\n")
                                result_text.see(END)
                        else:
                            result_text.insert(END, f"  Not enough data points for 3-month analysis\n")
                            result_text.see(END)
                        
                        # Check if there's a recent break that's still valid (within KEEP_3M_BREAK_DAYS)
                        if not break_3m and stock in detection_history.get(current_date, {}):
                            stock_history = detection_history[current_date].get(stock, {})
                            if "3m_break_date" in stock_history:
                                break_date = datetime.strptime(stock_history["3m_break_date"], "%Y-%m-%d")
                                recent_dates = [d for d in available_dates if d <= latest_date]
                                if len(recent_dates) >= 2:  # Need at least 2 dates to calculate days since break
                                    # Find position of break date in available dates
                                    if break_date in recent_dates:
                                        break_idx = recent_dates.index(break_date)
                                        days_since_break = len(recent_dates) - break_idx - 1
                                        if days_since_break <= KEEP_3M_BREAK_DAYS:
                                            break_3m = True
                                            break_types["3m_break_date"] = stock_history["3m_break_date"]
                                            break_types["3m_days_since"] = days_since_break
                        
                        if break_3m:
                            broke_high = True
                            if "3m_days_since" in break_types:
                                break_reasons.append(f"3 Months High (Day {break_types['3m_days_since']} of {KEEP_3M_BREAK_DAYS})")
                            else:
                                break_reasons.append("3 Months High (New Break)")
                    
                    # Save breaks to history
                    if broke_high:
                        detected_stocks.append((stock, break_reasons, latest_close))
                        if stock not in detection_history[current_date]:
                            detection_history[current_date][stock] = {}
                        
                        # Update break dates in history
                        for key, value in break_types.items():
                            detection_history[current_date][stock][key] = value
                else:
                    result_text.insert(END, f"  No data available for {stock}\n")
                    result_text.see(END)
            else:
                result_text.insert(END, f"  API error for {stock}: {response.status_code}\n")
                result_text.see(END)
            
            # Update UI periodically
            result_text.update()
            
        except Exception as e:
            result_text.insert(END, f"Error processing {stock}: {str(e)}\n")
            result_text.see(END)
    
    # Save updated detection history
    save_detection_history(detection_history)
    
    # Clear the result text and only show the detected stocks
    result_text.delete(1.0, END)
    
    # Show detected stocks
    if detected_stocks:
        result_text.insert(END, "Detected stocks breaking high price:\n\n")
        for stock, reasons, close in detected_stocks:
            result_text.insert(END, f"{stock}: {', '.join(reasons)} - Close: {close:.2f}\n")
    else:
        result_text.insert(END, "No stocks breaking high price detected.\n")
    
    # Show summary
    result_text.insert(END, f"\nDetection complete. Found {len(detected_stocks)} stocks breaking high price.\n")
    result_text.see(END)

def open_generator_window():
    """Open a new window for the generator"""
    generator_window = ttk.Toplevel(title="Break High Price Detector")
    generator_window.geometry("600x500")
    
    # Create a frame for the options
    options_frame = ttk.Frame(generator_window)
    options_frame.pack(fill=X, padx=20, pady=20)
    
    # Options
    ttk.Label(options_frame, text="Select Break High Period Options:", font=("Helvetica", 12)).pack(anchor=W)
    
    options = {
        "5_days": ttk.BooleanVar(),
        "1_month": ttk.BooleanVar(),
        "3_months": ttk.BooleanVar()
    }
    
    # Checkboxes
    ttk.Checkbutton(options_frame, text="5 Days High Price", variable=options["5_days"]).pack(anchor=W, pady=5)
    ttk.Checkbutton(options_frame, text="1 Month High Price", variable=options["1_month"]).pack(anchor=W, pady=5)
    ttk.Checkbutton(options_frame, text="3 Months High Price", variable=options["3_months"]).pack(anchor=W, pady=5)
    
    # Button frame
    button_frame = ttk.Frame(options_frame)
    button_frame.pack(fill=X, pady=10)
    
    # Results frame
    results_frame = ttk.Frame(generator_window)
    results_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
    
    # Results text area
    result_text = ttk.Text(results_frame, wrap=WORD, height=15)
    result_text.pack(fill=BOTH, expand=True, side=LEFT)
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(results_frame, command=result_text.yview)
    scrollbar.pack(fill=Y, side=RIGHT)
    result_text.config(yscrollcommand=scrollbar.set)
    
    # Run button
    run_button = ttk.Button(
        button_frame, 
        text="Run Detection", 
        bootstyle="success",
        command=lambda: threading.Thread(
            target=detect_break_high_price,
            args=(
                {k: v.get() for k, v in options.items()},
                result_text
            ),
            daemon=True
        ).start()
    )
    run_button.pack(side=LEFT, padx=5)

def show_main_page():
    # Remove API check elements
    for widget in center_frame.winfo_children():
        widget.destroy()
    
    # Reset center frame
    center_frame.pack_forget()
    center_frame.place_forget()
    
    # Main content frame
    main_frame = ttk.Frame(root)
    main_frame.pack(expand=True, fill=BOTH, padx=20, pady=20)
    
    # Header frame
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=X, pady=(0, 20))
    
    # Header title
    header_title = ttk.Label(header_frame, text="Trading Plan Generator", font=("Helvetica", 14, "bold"))
    header_title.pack(side=LEFT)
    
    # Create button
    create_button = ttk.Button(header_frame, text="Create", bootstyle="primary", command=open_generator_window)
    create_button.pack(side=RIGHT)

def check_api_availability(max_retries=10):
    base_url = "https://yfinance-web-indonesia-data.vercel.app"
    endpoints = [
        f"{base_url}/api/stocks?start_date=2023-01-01",
        f"{base_url}/api/stocks/BBCA?start_date=2023-01-01"
    ]

    for attempt in range(max_retries):
        for endpoint_url in endpoints:
            try:
                response = requests.get(endpoint_url)
                if response.status_code == 200:
                    root.after(0, lambda: api_status_label.config(text="API is available!"))
                    spinner.stop()
                    # Show main page after successful API check
                    root.after(1000, show_main_page)
                    return
                else:
                    raise Exception("API not available")
            except Exception as e:
                continue

        if attempt == max_retries - 1:
            root.after(0, lambda: api_status_label.config(text="API is not available!"))
            spinner.stop()

def start_api_check():
    threading.Thread(target=check_api_availability, daemon=True).start()

root.after(100, start_api_check)
root.mainloop()