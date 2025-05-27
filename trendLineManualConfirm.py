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
import traceback # For error printing
from sklearn.cluster import KMeans # Added for K-Means clustering

# --- Helper functions based on articles ---

def center_toplevel_window(window):
    window.update_idletasks() 
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    window_width = window.winfo_width()
    window_height = window.winfo_height()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    window.geometry(f'+{x}+{y}')

# --- K-Means Helper Function (Optional - can be integrated directly) ---
# Placeholder if more complex K-Means logic is needed separately
# def calculate_kmeans_sr_levels(price_data_series, n_clusters=6):
#     if len(price_data_series) < n_clusters:
#         print("Not enough data points for K-Means clustering.")
#         return []
#     try:
#         kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
#         kmeans.fit(price_data_series.values.reshape(-1, 1))
#         sr_levels = sorted(kmeans.cluster_centers_.flatten())
#         return sr_levels
#     except Exception as e:
#         print(f"K-Means calculation failed: {e}")
#         return []

# --- Main Chart Generation Function ---
def generate_candlestick_chart(stock_symbol, parent_tk_frame, show_kmeans_sr_lines=True):
    """
    Generates a candlestick chart for the given stock symbol for the last 1 year
    and embeds it into the parent_tk_frame.
    Includes K-Means based support/resistance lines if show_kmeans_sr_lines is True.
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

        df_from_api = pd.DataFrame(stock_data["historical_data"])
        if df_from_api.empty:
            print(f"DataFrame empty for {stock_symbol}.")
            return None

        df_for_plotting = df_from_api.copy()
        df_for_plotting['Date'] = pd.to_datetime(df_for_plotting['date'])
        df_for_plotting.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        }, inplace=True)
        df_for_plotting = df_for_plotting[['Date', 'Open', 'High', 'Low', 'Close', 'Volume']]
        df_for_plotting = df_for_plotting.astype({'Open': float, 'High': float, 'Low': float, 'Close': float, 'Volume': float})
        df_for_plotting.sort_values(by='Date', inplace=True)
        df_for_plotting.set_index('Date', inplace=True)

        alines_data = []
        line_colors = []

        # --- K-Means Support/Resistance Calculation ---
        if show_kmeans_sr_lines:
            n_clusters_kmeans = 6 # Number of clusters for K-Means
            
            # Prepare data for K-Means (using average of High and Low prices)
            if not df_for_plotting.empty and all(col in df_for_plotting for col in ['High', 'Low']):
                # Use a copy to avoid SettingWithCopyWarning if df_for_plotting is a slice
                prices_df_for_kmeans = df_for_plotting[['High', 'Low']].copy()
                prices_for_kmeans_series = (prices_df_for_kmeans['High'] + prices_df_for_kmeans['Low']) / 2
                
                if len(prices_for_kmeans_series) >= n_clusters_kmeans:
                    try:
                        kmeans = KMeans(n_clusters=n_clusters_kmeans, random_state=42, n_init='auto')
                        kmeans.fit(prices_for_kmeans_series.values.reshape(-1, 1))
                        sr_levels = sorted(kmeans.cluster_centers_.flatten())
                        
                        date_start_for_lines = df_for_plotting.index[0]
                        date_end_for_lines = df_for_plotting.index[-1]
                        
                        for level in sr_levels:
                            alines_data.append([(date_start_for_lines, level), (date_end_for_lines, level)])
                            line_colors.append('blue') # Changed color to blue
                        print(f"INFO: {stock_symbol} - K-Means S/R lines added ({len(sr_levels)} levels).")
                    except Exception as kmeans_exc:
                        print(f"ERROR: {stock_symbol} - K-Means calculation failed: {kmeans_exc}")
                        traceback.print_exc()
                else:
                    print(f"INFO: {stock_symbol} - Not enough data points for K-Means ({len(prices_for_kmeans_series)} points, need {n_clusters_kmeans}).")
            else:
                print(f"INFO: {stock_symbol} - Data for K-Means not available (High/Low columns missing or empty DataFrame).")
        # --- End of K-Means Support/Resistance Calculation ---
        
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', inherit=True)
        s = mpf.make_mpf_style(base_mpf_style='nightclouds', marketcolors=mc,
                               figcolor='k', facecolor='k',
                               rc={'xtick.labelsize': 0, 'ytick.labelsize': 8, 
                                   'axes.titlesize': 10, 'axes.labelsize': 8,
                                   'xtick.color':'k', 'axes.labelcolor':'lightgray',
                                   'axes.edgecolor':'gray', 'axes.titlecolor':'lightgray', 
                                   'ytick.color':'lightgray', 'axes.facecolor':'k'})
        
        fig = plt.Figure(facecolor='k')
        gs = fig.add_gridspec(nrows=2, ncols=1, height_ratios=[3, 1], hspace=0.0)
        ax_price = fig.add_subplot(gs[0,0], facecolor='k')
        ax_volume = fig.add_subplot(gs[1,0], facecolor='k', sharex=ax_price)

        plot_kwargs = {
            'type': 'candle',
            'style': s,
            'ax': ax_price,
            'volume': ax_volume,
            'show_nontrading': False
        }
        if alines_data:
            plot_kwargs['alines'] = dict(alines=alines_data, 
                                         colors=line_colors, 
                                         linestyle='dashed',
                                         linewidths=0.5)

        mpf.plot(df_for_plotting, **plot_kwargs)
        
        ax_price.set_xticklabels([])
        ax_price.set_xticks([])
        ax_price.set_xlabel('')
        ax_volume.set_xticklabels([])
        ax_volume.set_xticks([])
        ax_volume.set_xlabel('')
        
        ax_price.yaxis.label.set_color('lightgray')
        ax_volume.yaxis.label.set_color('lightgray')

        fig.suptitle(f"{stock_symbol} - Last 1 Year (K-Means S/R)", color='lightgray', fontsize=10)
        fig.subplots_adjust(bottom=0.05, top=0.92)

        canvas = FigureCanvasTkAgg(fig, master=parent_tk_frame)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=TOP, fill=BOTH, expand=True)
        canvas.draw()

        return canvas

    except requests.exceptions.RequestException as e:
        print(f"API request error for {stock_symbol} chart: {e}")
        return None
    except ImportError as e:
        print(f"ImportError during chart generation: {e}")
        traceback.print_exc()
        error_label = ttk.Label(parent_tk_frame, text=f"Error: A required library might be missing (e.g., scikit-learn).", foreground="red")
        error_label.pack(pady=10, fill=BOTH, expand=True)
        return None
    except Exception as e:
        print(f"Error generating candlestick chart for {stock_symbol}: {e}")
        traceback.print_exc()
        return None

# --- Trend Line Confirmation Window ---
def open_trend_line_confirmation_window(parent_window_for_dialogs, all_detected_stocks, summary_text_original, final_status_original, original_completion_callback, original_set_continue_button_state_callback, original_shared_detected_stocks_list_ref):
    
    confirmed_stocks_accumulator = []
    stocks_to_review = list(all_detected_stocks) 
    
    # Store canvas objects to manage them
    current_chart_canvas_obj = None

    def _show_next_stock_confirmation(current_stock_list_to_review):
        nonlocal current_chart_canvas_obj # To manage destroying old canvas

        if current_chart_canvas_obj and current_chart_canvas_obj.get_tk_widget().winfo_exists():
            current_chart_canvas_obj.get_tk_widget().destroy()
            plt.close(current_chart_canvas_obj.figure) # Close the matplotlib figure
            current_chart_canvas_obj = None

        if not current_stock_list_to_review:
            original_shared_detected_stocks_list_ref.clear()
            original_shared_detected_stocks_list_ref.extend(confirmed_stocks_accumulator)

            num_confirmed = len(confirmed_stocks_accumulator)
            num_total_detected = len(all_detected_stocks)
            
            updated_summary_text = f"K-Means S/R Line Review Complete. {num_confirmed} of {num_total_detected} stocks confirmed for plan generation.\n\n"
            if confirmed_stocks_accumulator:
                updated_summary_text += "Confirmed Stocks:\n"
                for stock_data in confirmed_stocks_accumulator:
                    updated_summary_text += f"- {stock_data[0]}\n" # Assuming stock_data is a tuple/list with name at index 0
            
            updated_final_status = f"Proceeding with {num_confirmed} confirmed stocks."
            if num_confirmed == 0:
                updated_final_status = "No stocks were confirmed after K-Means S/R line review. No plans will be generated."

            original_completion_callback(confirmed_stocks_accumulator, updated_summary_text, updated_final_status)
            
            if confirmed_stocks_accumulator: 
                original_set_continue_button_state_callback(True)
            else:
                original_set_continue_button_state_callback(False)
            
            # Explicitly destroy dialog if it's still alive (e.g. if the last stock was processed)
            # This assumes the dialog is tied to the lifecycle of _show_next_stock_confirmation's calls.
            # It's better to destroy the dialog in handle_decision after the last stock.
            # For now, this path means the process is complete.
            if 'confirmation_dialog' in locals() and confirmation_dialog.winfo_exists():
                 confirmation_dialog.destroy()
            return

        stock_to_confirm_data = current_stock_list_to_review.pop(0)
        stock_name = stock_to_confirm_data[0] # Assuming stock name is the first element

        confirmation_dialog = ttk.Toplevel(parent_window_for_dialogs)
        confirmation_dialog.title(f"Confirm K-Means S/R: {stock_name}")
        confirmation_dialog.geometry("1280x760") # Slightly increased height for checkbox
        confirmation_dialog.transient(parent_window_for_dialogs)
        confirmation_dialog.grab_set()
        confirmation_dialog.resizable(True, True)

        dialog_main_frame = ttk.Frame(confirmation_dialog, padding=15)
        dialog_main_frame.pack(fill=BOTH, expand=True)
        
        # --- UI Elements ---
        stock_label = ttk.Label(dialog_main_frame, text=f"Stock: {stock_name}", font=("Helvetica", 14, "bold"))
        stock_label.pack(pady=(0,5), side=TOP)

        show_kmeans_sr_var = ttk.BooleanVar(value=True) # Default to show lines

        chart_frame = ttk.Frame(dialog_main_frame) # Frame to hold the chart
        chart_frame.pack(pady=5, fill=BOTH, expand=True, side=TOP)
        
        # Function to redraw chart (needed for checkbox toggle)
        def redraw_chart():
            nonlocal current_chart_canvas_obj
            # Clear previous chart from chart_frame
            for widget in chart_frame.winfo_children():
                widget.destroy()
            if current_chart_canvas_obj and current_chart_canvas_obj.get_tk_widget().winfo_exists():
                 current_chart_canvas_obj.get_tk_widget().destroy()
                 plt.close(current_chart_canvas_obj.figure)

            current_chart_canvas_obj = generate_candlestick_chart(stock_name, chart_frame, show_kmeans_sr_var.get())
            if not current_chart_canvas_obj:
                error_label = ttk.Label(chart_frame, text=f"Could not load chart for {stock_name}.", foreground="red")
                error_label.pack(pady=10, fill=BOTH, expand=True)

        kmeans_checkbutton = ttk.Checkbutton(dialog_main_frame, text="Show K-Means S/R Lines", variable=show_kmeans_sr_var, command=redraw_chart)
        kmeans_checkbutton.pack(side=TOP, pady=(0,5))
        
        # Initial chart draw
        redraw_chart()

        buttons_frame = ttk.Frame(dialog_main_frame)
        buttons_frame.pack(fill=X, pady=(10,0), side=BOTTOM)

        def handle_decision(confirmed_this_stock):
            if confirmed_this_stock:
                confirmed_stocks_accumulator.append(stock_to_confirm_data) # Append the original data
                print(f"DEBUG: {stock_name} confirmed YES (K-Means S/R).")
            else:
                print(f"DEBUG: {stock_name} confirmed NO (K-Means S/R).")
            
            # Destroy current dialog and move to next or finish
            confirmation_dialog.destroy() # Destroy this specific dialog instance
            _show_next_stock_confirmation(current_stock_list_to_review) # Process next stock

        no_button = ttk.Button(buttons_frame, text="No (Exclude)", bootstyle="danger", command=lambda: handle_decision(False))
        no_button.pack(side=RIGHT, padx=10)

        yes_button = ttk.Button(buttons_frame, text="Yes (Include)", bootstyle="success", command=lambda: handle_decision(True))
        yes_button.pack(side=RIGHT, padx=10)
        
        center_toplevel_window(confirmation_dialog)
        confirmation_dialog.focus_set()
        
        # Ensure the dialog closes properly if the window 'X' is clicked
        def on_dialog_close():
            print(f"DEBUG: Confirmation dialog for {stock_name} closed via window manager.")
            # Treat as 'No' or some other default action if needed, or just close.
            # For now, let it close and the main flow might be interrupted.
            # To ensure flow, one might want to trigger handle_decision(False) or similar.
            # However, grab_set should prevent interaction with parent until this is closed.
            if current_chart_canvas_obj and current_chart_canvas_obj.get_tk_widget().winfo_exists():
                 current_chart_canvas_obj.get_tk_widget().destroy()
                 plt.close(current_chart_canvas_obj.figure)
            confirmation_dialog.destroy()
            # Potentially call _show_next_stock_confirmation([]) to terminate early,
            # or just let it hang if parent window is also closed.
            # For robustness, this should ideally not skip the rest of the stocks.
            # A simple destroy might be okay if user intends to abort.

        confirmation_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)


    if not all_detected_stocks:
        original_shared_detected_stocks_list_ref.clear()
        original_completion_callback([], "No stocks were initially detected for K-Means S/R line confirmation.", "No action taken.")
        original_set_continue_button_state_callback(False)
        return
        
    _show_next_stock_confirmation(stocks_to_review) 