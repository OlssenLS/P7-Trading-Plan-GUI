import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from datetime import datetime, timedelta
import requests
import pandas as pd
import matplotlib
matplotlib.use("TkAgg") # Ensure TkAgg backend is used
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import mplfinance as mpf
import numpy as np
# from scipy import stats # Removed: numpy.polyfit is used instead
import traceback # For error printing in generate_candlestick_chart

# --- Helper functions based on the Medium article ---

def isPivot(df_for_pivot, candle_index, window):
    """
    Detects if a candle is a pivot/fractal point.
    Args:
        df_for_pivot: DataFrame containing the price data (must have 'Low' and 'High' columns)
        candle_index: index of the candle in the DataFrame
        window: number of candles before and after the current candle to consider
    Returns:
        1 if pivot high, 2 if pivot low, 3 if both, 0 otherwise.
    """
    if candle_index - window < 0 or candle_index + window >= len(df_for_pivot):
        return 0

    pivotHigh = 1
    pivotLow = 2
    # Ensure we are using .iloc for positional indexing if candle_index is an integer offset
    # If candle_index is a label (like a datetime), df_for_pivot.loc[candle_index] is fine
    # Assuming candle_index here is an integer offset for .iloc access
    
    # Determine actual iloc-based indices for window
    start_iloc = max(0, candle_index - window)
    end_iloc = min(len(df_for_pivot), candle_index + window + 1)
    
    current_candle_low = df_for_pivot.iloc[candle_index]['Low']
    current_candle_high = df_for_pivot.iloc[candle_index]['High']

    for i in range(start_iloc, end_iloc):
        if i == candle_index:
            continue
        if current_candle_low > df_for_pivot.iloc[i]['Low']:
            pivotLow = 0
        if current_candle_high < df_for_pivot.iloc[i]['High']:
            pivotHigh = 0
    
    if pivotHigh and pivotLow:
        return 3
    elif pivotHigh:
        return 1
    elif pivotLow:
        return 2
    else:
        return 0

def collect_channel(df_for_channel, candle_index, backcandles, window):
    """
    Analyzes a window of candles to determine linear regression lines for high and low channels.
    Args:
        df_for_channel: DataFrame with price data.
        candle_index: The CURRENT candle index for which we are looking back to define channels.
        backcandles: Number of candles to look back from candle_index to define the channel.
        window: Window for pivot detection.
    Returns:
        Tuple (sl_lows, interc_lows, r_sq_l, num_low_pivots,
               sl_highs, interc_highs, r_sq_h, num_high_pivots)
    """
    start_index_for_pivots = max(0, candle_index - backcandles)
    end_index_for_pivots = candle_index + 1

    localdf_for_pivots = df_for_channel.iloc[start_index_for_pivots:end_index_for_pivots].copy()

    if localdf_for_pivots.empty or len(localdf_for_pivots) < window * 2 + 1:
        return (0, 0, 0, 0, 0, 0, 0, 0) # sl, int, rsq, num_pivots for low & high

    pivots = [isPivot(localdf_for_pivots, i, window) for i in range(len(localdf_for_pivots))]
    localdf_for_pivots['Pivot'] = pivots

    highs_df = localdf_for_pivots[localdf_for_pivots['Pivot'] == 1] # Pivot High
    lows_df = localdf_for_pivots[(localdf_for_pivots['Pivot'] == 2) | (localdf_for_pivots['Pivot'] == 3)] # Pivot Low or Both

    idxhighs = highs_df.index.astype(np.int64)
    high_prices = highs_df['High'].values
    num_high_pivots = len(high_prices)

    idxlows = lows_df.index.astype(np.int64)
    low_prices = lows_df['Low'].values
    num_low_pivots = len(low_prices)

    sl_lows, interc_lows, r_sq_l = 0, 0, 0
    sl_highs, interc_highs, r_sq_h = 0, 0, 0

    min_pivots_for_line = 2

    if num_low_pivots >= min_pivots_for_line:
        res_lows = np.polyfit(idxlows, low_prices, 1)
        sl_lows, interc_lows = res_lows[0], res_lows[1]
        y_pred_lows = sl_lows * idxlows + interc_lows
        ss_res_lows = np.sum((low_prices - y_pred_lows)**2)
        ss_tot_lows = np.sum((low_prices - np.mean(low_prices))**2)
        r_sq_l = 1 - (ss_res_lows / ss_tot_lows) if ss_tot_lows > 0 else 0

    if num_high_pivots >= min_pivots_for_line:
        res_highs = np.polyfit(idxhighs, high_prices, 1)
        sl_highs, interc_highs = res_highs[0], res_highs[1]
        y_pred_highs = sl_highs * idxhighs + interc_highs
        ss_res_highs = np.sum((high_prices - y_pred_highs)**2)
        ss_tot_highs = np.sum((high_prices - np.mean(high_prices))**2)
        r_sq_h = 1 - (ss_res_highs / ss_tot_highs) if ss_tot_highs > 0 else 0
        
    return (sl_lows, interc_lows, r_sq_l, num_low_pivots,
            sl_highs, interc_highs, r_sq_h, num_high_pivots)

# --- End of helper functions ---

# Moved from main.py
def generate_candlestick_chart(stock_symbol, parent_tk_frame):
    """
    Generates a candlestick chart for the given stock symbol for the last 6 months
    and embeds it into the parent_tk_frame.
    Returns the FigureCanvasTkAgg widget or None.
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365) # Approx 1 year
        
        api_url = f"https://yfinance-web-indonesia-data.vercel.app/api/stocks/{stock_symbol}?start_date={start_date.strftime('%Y-%m-%d')}&end_date={end_date.strftime('%Y-%m-%d')}"
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        stock_data = response.json()

        if not stock_data or "historical_data" not in stock_data or not stock_data["historical_data"]:
            print(f"No historical data for {stock_symbol} for chart.")
            return None

        df = pd.DataFrame(stock_data["historical_data"])
        if df.empty:
            print(f"DataFrame empty for {stock_symbol}.")
            return None

        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.astype(float)

        # Custom mplfinance style
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', inherit=True)
        s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc,
                               figcolor='k', facecolor='k',
                               rc={'xtick.labelsize': 0, 'ytick.labelsize': 8, 
                                   'axes.titlesize': 10, 'axes.labelsize': 8,
                                   'xtick.color':'k', 'axes.labelcolor':'lightgray',
                                   'axes.edgecolor':'gray', 'axes.titlecolor':'lightgray', 
                                   'ytick.color':'lightgray', 'axes.facecolor':'k'})

        # --- Trend Line Calculation using new channel logic ---
        alines_data = []
        line_colors = []

        # Parameters for channel detection (can be tuned)
        backcandles_channel = 60 # Number of past candles to consider for channel formation
        window_pivot = 4       # Window for pivot detection (n candles before and after)

        # We need to pass the DataFrame with 'Low' and 'High' columns to isPivot and collect_channel
        # The 'collect_channel' function expects candle_index to be the *current* end point for channel calculation.
        # For plotting, we usually want the channel over the whole period or a significant recent part.
        # Let's try to calculate channels based on pivots found in the entire df.
        # The article's 'collect_channel' is designed to be called for *each* candle to see if a breakout is occurring.
        # For visualization, we might want one set of channels for the displayed period.

        # The df needs integer-based index for polyfit if we use df.index directly.
        # Or, we can use np.arange(len(df)) for x-values in regression.
        # Let's use np.arange(len(df)) for regression to keep it simple.
        df_for_channels = df.reset_index() # Adds 'index' column, keeps 'date'
        
        # Calculate pivots for the entire DataFrame first
        # df_for_channels['Pivot'] = [isPivot(df_for_channels, i, window_pivot) for i in range(len(df_for_channels))]

        # Call collect_channel. The 'candle_index' here means the end of the period for which channel is calculated.
        # For a static chart, we calculate it once for the whole period, so candle_index = len(df_for_channels) - 1
        
        # Reset index for df_for_channels so iloc and index based operations are consistent
        # This also means 'idxhighs' and 'idxlows' in collect_channel will be simple integer sequences
        df_reg = df.copy()
        df_reg.reset_index(drop=True, inplace=True) # Now index is 0, 1, 2...

        sl_lows, interc_lows, r_sq_l, num_low_pivots, \
        sl_highs, interc_highs, r_sq_h, num_high_pivots = collect_channel(
            df_reg,
            len(df_reg) - 1,
            backcandles_channel,
            window_pivot
        )

        # Debug prints
        print(f"DEBUG: Stock {stock_symbol} - Lows: Pivots={num_low_pivots}, Slope={sl_lows:.2f}, Intercept={interc_lows:.2f}, R^2={r_sq_l:.2f}")
        print(f"DEBUG: Stock {stock_symbol} - Highs: Pivots={num_high_pivots}, Slope={sl_highs:.2f}, Intercept={interc_highs:.2f}, R^2={r_sq_h:.2f}")

        min_pivots_for_drawing = 2 # Consistent with collect_channel logic

        # Define the drawing range (last backcandles_channel period)
        numeric_idx_end_draw = len(df_reg) - 1
        numeric_idx_start_draw = max(0, numeric_idx_end_draw - backcandles_channel)
        
        date_start_draw = df.index[numeric_idx_start_draw]
        date_end_draw = df.index[numeric_idx_end_draw]

        # Placeholder for support line data if drawn, needed for resistance check
        support_line_drawn = False
        y_start_low_check, y_end_low_check = 0, 0

        if num_low_pivots >= min_pivots_for_drawing:
            y_start_low = sl_lows * numeric_idx_start_draw + interc_lows
            y_end_low = sl_lows * numeric_idx_end_draw + interc_lows
            alines_data.append([(date_start_draw, y_start_low), (date_end_draw, y_end_low)])
            line_colors.append('blue') 
            support_line_drawn = True
            y_start_low_check = y_start_low
            y_end_low_check = y_end_low
        else:
            print(f"INFO: {stock_symbol} - Not enough low pivots ({num_low_pivots}) to draw support line.")

        if num_high_pivots >= min_pivots_for_drawing:
            y_start_high = sl_highs * numeric_idx_start_draw + interc_highs
            y_end_high = sl_highs * numeric_idx_end_draw + interc_highs
            
            draw_resistance_line = True
            if support_line_drawn:
                # Check 1: Resistance entirely below support in the drawn segment
                if y_start_high < y_start_low_check and y_end_high < y_end_low_check:
                    print(f"WARNING: {stock_symbol} - Resistance line is entirely below support line for the drawn segment. Not drawing resistance line.")
                    draw_resistance_line = False
                # Check 2: Lines cross within the drawn segment
                # Corrected crossing logic:
                # (starts above, ends below) OR (starts below, ends above)
                elif (y_start_high > y_start_low_check and y_end_high < y_end_low_check) or \
                     (y_start_high < y_start_low_check and y_end_high > y_end_low_check):
                     print(f"WARNING: {stock_symbol} - Resistance line crosses support line within the drawn segment. Not drawing resistance line.")
                     draw_resistance_line = False

            if draw_resistance_line:
                alines_data.append([(date_start_draw, y_start_high), (date_end_draw, y_end_high)])
                line_colors.append('red')
        else:
            print(f"INFO: {stock_symbol} - Not enough high pivots ({num_high_pivots}) to draw resistance line.")

        fig = plt.Figure(facecolor='k')
        gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 1], hspace=0.0)
        ax_price = fig.add_subplot(gs[0,0], facecolor='k')
        ax_volume = fig.add_subplot(gs[1,0], facecolor='k', sharex=ax_price)

        mpf.plot(df, type='candle', style=s, 
                 ax=ax_price,
                 volume=ax_volume,
                 show_nontrading=False,
                 alines=dict(alines=alines_data, colors=line_colors)
                )
        
        ax_price.set_xticklabels([])
        ax_price.set_xticks([])
        ax_price.set_xlabel('')
        ax_volume.set_xticklabels([])
        ax_volume.set_xticks([])
        ax_volume.set_xlabel('')
        
        ax_price.yaxis.label.set_color('lightgray')
        ax_volume.yaxis.label.set_color('lightgray')

        fig.suptitle(f"{stock_symbol} - Last 6 Months", color='lightgray', fontsize=10)
        fig.subplots_adjust(bottom=0.05, top=0.92)

        canvas = FigureCanvasTkAgg(fig, master=parent_tk_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=TOP, fill=BOTH, expand=True)
        canvas.draw()

        return canvas

    except requests.exceptions.RequestException as e:
        print(f"API request error for {stock_symbol} chart: {e}")
        return None
    except Exception as e:
        print(f"Error generating candlestick chart for {stock_symbol}: {e}")
        traceback.print_exc()
        return None

# Moved from main.py
def open_trend_line_confirmation_window(parent_window_for_dialogs, all_detected_stocks, summary_text_original, final_status_original, original_completion_callback, original_set_continue_button_state_callback, original_shared_detected_stocks_list_ref):
    
    confirmed_stocks_accumulator = []
    stocks_to_review = list(all_detected_stocks) 

    def _show_next_stock_confirmation(current_stock_list_to_review):
        if not current_stock_list_to_review:
            original_shared_detected_stocks_list_ref.clear()
            original_shared_detected_stocks_list_ref.extend(confirmed_stocks_accumulator)

            num_confirmed = len(confirmed_stocks_accumulator)
            num_total_detected = len(all_detected_stocks)
            
            updated_summary_text = f"Trend Line Review Complete. {num_confirmed} of {num_total_detected} stocks confirmed for plan generation.\n\n"
            if confirmed_stocks_accumulator:
                updated_summary_text += "Confirmed Stocks:\n"
                for stock_data in confirmed_stocks_accumulator:
                    updated_summary_text += f"- {stock_data[0]}\n"
            
            updated_final_status = f"Proceeding with {num_confirmed} confirmed stocks."
            if num_confirmed == 0:
                updated_final_status = "No stocks were confirmed after trend line review. No plans will be generated."

            original_completion_callback(confirmed_stocks_accumulator, updated_summary_text, updated_final_status)
            
            if confirmed_stocks_accumulator: 
                original_set_continue_button_state_callback(True)
            else:
                original_set_continue_button_state_callback(False)
            return

        stock_to_confirm = current_stock_list_to_review.pop(0)
        stock_name = stock_to_confirm[0]

        confirmation_dialog = ttk.Toplevel(parent_window_for_dialogs)
        confirmation_dialog.title(f"Confirm Trend Line: {stock_name}")
        confirmation_dialog.geometry("1280x720")
        confirmation_dialog.transient(parent_window_for_dialogs)
        confirmation_dialog.grab_set()
        confirmation_dialog.resizable(True, True)

        dialog_main_frame = ttk.Frame(confirmation_dialog, padding=15)
        dialog_main_frame.pack(fill=BOTH, expand=True)

        ttk.Label(dialog_main_frame, text=f"Stock: {stock_name}", font=("Helvetica", 14, "bold")).pack(pady=(0,10), side=TOP)
        
        chart_frame = ttk.Frame(dialog_main_frame)
        chart_frame.pack(pady=10, fill=BOTH, expand=True, side=TOP)

        chart_canvas_obj = generate_candlestick_chart(stock_name, chart_frame)
        
        if not chart_canvas_obj:
            error_label = ttk.Label(chart_frame, text=f"Could not load chart for {stock_name}.", foreground="red")
            error_label.pack(pady=10, fill=BOTH, expand=True)

        buttons_frame = ttk.Frame(dialog_main_frame)
        buttons_frame.pack(fill=X, pady=(10,0))

        def handle_decision(confirmed_this_stock):
            if confirmed_this_stock:
                confirmed_stocks_accumulator.append(stock_to_confirm)
                print(f"DEBUG: {stock_name} confirmed YES.")
            else:
                print(f"DEBUG: {stock_name} confirmed NO.")
            
            confirmation_dialog.destroy()
            _show_next_stock_confirmation(current_stock_list_to_review)

        no_button = ttk.Button(buttons_frame, text="No (Exclude)", bootstyle="danger", command=lambda: handle_decision(False))
        no_button.pack(side=RIGHT, padx=10)

        yes_button = ttk.Button(buttons_frame, text="Yes (Include)", bootstyle="success", command=lambda: handle_decision(True))
        yes_button.pack(side=RIGHT, padx=10)
        
        confirmation_dialog.update_idletasks()
        x = parent_window_for_dialogs.winfo_x() + (parent_window_for_dialogs.winfo_width() // 2) - (confirmation_dialog.winfo_width() // 2)
        y = parent_window_for_dialogs.winfo_y() + (parent_window_for_dialogs.winfo_height() // 2) - (confirmation_dialog.winfo_height() // 2)
        confirmation_dialog.geometry(f"+{x}+{y}")
        confirmation_dialog.focus_set()

    if not all_detected_stocks:
        original_shared_detected_stocks_list_ref.clear()
        original_completion_callback([], "No stocks were initially detected for trend line confirmation.", "No action taken.")
        original_set_continue_button_state_callback(False)
        return
        
    _show_next_stock_confirmation(stocks_to_review) 