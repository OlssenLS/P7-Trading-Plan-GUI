import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import requests
import os
import pandas as pd
from datetime import datetime, timedelta
import json
from tkinter import simpledialog, filedialog
import io

# Charting imports
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import mplfinance as mpf

# Module Imports
from breakHighPriceDetection import detect_break_high_price, DATA_DIR, STOCKS_FILE, get_stock_list
from autoGenerateTradingPlan import generate_plans_for_stocks, display_plans_in_main_area_placeholder
from filterManager import FilterManager
from trendLineManualConfirm import open_trend_line_confirmation_window

SAVED_PLANS_FILE = os.path.join(DATA_DIR, "saved_trading_plans.json")

def center_toplevel_window(window):
    window.update_idletasks() 
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    window_width = window.winfo_width()
    window_height = window.winfo_height()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    window.geometry(f'+{x}+{y}')

root = ttk.Window(themename="superhero")
root.title("Trading Plan Generator")
root.geometry("800x600")
root.resizable(True, True)
center_toplevel_window(root)

center_frame = ttk.Frame(root)
center_frame.pack(expand=True, fill=BOTH)
center_frame.place(relx=0.5, rely=0.5, anchor=CENTER)

# --- API check ---
api_status_label = ttk.Label(center_frame, text="Checking API availability...")
api_status_label.grid(column=0, row=1, padx=10, pady=10)
spinner = ttk.Progressbar(center_frame, orient=HORIZONTAL, length=300, mode="indeterminate")
spinner.grid(column=0, row=0, padx=10, pady=10)
spinner.start()

os.makedirs(DATA_DIR, exist_ok=True)

main_plan_display_treeview = None

# --- Plan File Operations (Load/Save/Delete All) ---
def load_plans_from_file():
    """Loads trading plans from the JSON file."""
    if not os.path.exists(SAVED_PLANS_FILE):
        return []
    try:
        with open(SAVED_PLANS_FILE, "r") as f:
            plans = json.load(f)
            return plans if isinstance(plans, list) else []
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading plans from {SAVED_PLANS_FILE}: {e}")
        return []

def save_plans_to_file(new_plans_to_add):
    """Saves a list of new plans to the JSON file, updating existing or appending new."""
    existing_plans_list = load_plans_from_file()
    updated_plans_dict = {plan['stock']: plan for plan in existing_plans_list if 'stock' in plan}
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    for new_plan in new_plans_to_add:
        if 'stock' in new_plan:
            stock_key = new_plan['stock']
            if stock_key in updated_plans_dict:
                existing_plan = updated_plans_dict[stock_key]
                new_plan['creation_date'] = existing_plan.get('creation_date', current_time_str)
                updated_plans_dict[stock_key] = new_plan
            else:
                new_plan['creation_date'] = current_time_str
                updated_plans_dict[stock_key] = new_plan
        
    final_plans_list = list(updated_plans_dict.values())
    
    try:
        with open(SAVED_PLANS_FILE, "w") as f:
            json.dump(final_plans_list, f, indent=4)
        print(f"Plans saved to {SAVED_PLANS_FILE}")
        return True
    except IOError as e:
        print(f"Error saving plans to {SAVED_PLANS_FILE}: {e}")
        simpledialog.messagebox.showerror("Save Error", f"Could not save plans to file: {e}", parent=root)
        return False

def delete_all_saved_plans():
    """Deletes all saved trading plans from the file and clears the display."""
    global main_plan_display_treeview
    if not os.path.exists(SAVED_PLANS_FILE):
        simpledialog.messagebox.showinfo("No Plans", "There are no saved plans to delete.", parent=root)
        return

    confirm = simpledialog.messagebox.askyesno(
        "Confirm Delete", 
        "Are you sure you want to delete all saved trading plans? This action cannot be undone.",
        parent=root
    )
    if confirm:
        try:
            os.remove(SAVED_PLANS_FILE)
            simpledialog.messagebox.showinfo("Success", "All saved trading plans have been deleted.", parent=root)
            if main_plan_display_treeview:
                display_plans_in_main_area_placeholder([], main_plan_display_treeview)
        except OSError as e:
            simpledialog.messagebox.showerror("Error", f"Could not delete saved plans file: {e}", parent=root)
    else:
        simpledialog.messagebox.showinfo("Cancelled", "Delete operation cancelled.", parent=root)

# --- Generated Trading Plans Display Window ---
def show_generated_plans_window(parent_window, generated_plans, original_plan_window):
    """Open a new window to display generated trading plans and offer save/discard options."""
    if not generated_plans:
        simpledialog.messagebox.showinfo("No Plans", "No trading plans were generated.", parent=parent_window)
        return

    gen_plans_window = ttk.Toplevel(parent_window)
    gen_plans_window.title("Generated Trading Plans")
    gen_plans_window.transient(parent_window)
    gen_plans_window.grab_set()
    center_toplevel_window(gen_plans_window)

    main_gen_frame = ttk.Frame(gen_plans_window, padding=10)
    main_gen_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_gen_frame, text="Generated Trading Plans:", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0,10))

    columns = ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3")
    tree = ttk.Treeview(main_gen_frame, columns=columns, show="headings", height=10)
    
    tree.heading("stock", text="Stock")
    tree.heading("entry_price", text="Entry Price")
    tree.heading("stop_loss", text="Stop Loss")
    tree.heading("tp1", text="TP1")
    tree.heading("tp2", text="TP2")
    tree.heading("tp3", text="TP3")

    tree.column("stock", width=80, anchor=CENTER)
    tree.column("entry_price", width=100, anchor=CENTER)
    tree.column("stop_loss", width=100, anchor=CENTER)
    tree.column("tp1", width=100, anchor=CENTER)
    tree.column("tp2", width=100, anchor=CENTER)
    tree.column("tp3", width=100, anchor=CENTER)

    for plan in generated_plans:
        tree.insert("", END, values=([plan.get(col, "N/A") for col in columns]))

    tree.pack(fill=BOTH, expand=True, pady=5)

    scrollbar_tree = ttk.Scrollbar(main_gen_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar_tree.set)

    button_gen_frame = ttk.Frame(main_gen_frame)
    button_gen_frame.pack(fill=X, pady=(10, 0))

    def discard_action():
        gen_plans_window.destroy()

    discard_button = ttk.Button(button_gen_frame, text="Discard Plans", command=discard_action, bootstyle="danger")

    def save_action():
        global main_plan_display_treeview
        print("Saving generated plans...")
        
        if save_plans_to_file(generated_plans):
            simpledialog.messagebox.showinfo("Plans Saved", "Trading plans have been successfully saved.", parent=gen_plans_window)
            if main_plan_display_treeview:
                all_saved_plans = load_plans_from_file()
                display_plans_in_main_area_placeholder(all_saved_plans, main_plan_display_treeview)
            else:
                print("main_plan_display_treeview not initialized. Cannot refresh display.")
            
        gen_plans_window.destroy()

    def convert_to_spreadsheet_action():
        if not generated_plans:
            simpledialog.messagebox.showinfo("No Data", "No plans to convert.", parent=gen_plans_window)
            return

        try:
            df = pd.DataFrame(generated_plans)
            columns_to_drop = ['latest_close', 'latest_high_of_day', 'latest_low_of_day', 'notes', 'rr_tp1']
            df.drop(columns=columns_to_drop, inplace=True, errors='ignore')
            
            default_filename = f"trading_plans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Trading Plans as Excel",
                parent=gen_plans_window
            )
            if filepath:
                df.to_excel(filepath, index=False)
                simpledialog.messagebox.showinfo("Success", f"Plans successfully saved to {filepath}", parent=gen_plans_window)
        except Exception as e:
            simpledialog.messagebox.showerror("Error", f"Could not save to Excel: {e}", parent=gen_plans_window)

    convert_button = ttk.Button(button_gen_frame, text="Convert to Spreadsheet", command=convert_to_spreadsheet_action, bootstyle="info")
    convert_button.pack(side=LEFT, padx=5)
    discard_button.pack(side=LEFT, padx=5)

    save_button = ttk.Button(button_gen_frame, text="Save & Display Plans", command=save_action, bootstyle="success")
    save_button.pack(side=RIGHT, padx=5)

    if original_plan_window and original_plan_window.winfo_exists():
        original_plan_window.destroy()

# --- Trading Plan Setup Window (Stock Selection & Plan Type) ---
def open_trading_plan_window(parent_window, stocks_for_plan_generation_data, initial_plan_type="Swing Trader", plan_type_disabled=False, original_screener_window=None):
    """Open a new window to select stocks for trading plan generation."""
    if original_screener_window and original_screener_window.winfo_exists():
        original_screener_window.destroy()

    plan_window = ttk.Toplevel(parent_window)
    plan_window.title("Generate Trading Plan")
    plan_window.transient(parent_window)
    plan_window.grab_set()
    center_toplevel_window(plan_window)

    if not stocks_for_plan_generation_data:
        ttk.Label(plan_window, text="No stocks available or selected from screener for plan generation.", padding=20).pack()
        ttk.Button(plan_window, text="Close", command=plan_window.destroy).pack(pady=10)
        return

    main_frame = ttk.Frame(plan_window, padding=10)
    main_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_frame, text="Select stocks to generate trading plan for:", font=("Helvetica", 10, "bold")).pack(anchor=W, pady=(0, 10))

    stocks_outer_frame = ttk.Frame(main_frame)
    stocks_outer_frame.pack(fill=BOTH, expand=True, pady=5)
    
    selected_stocks_vars = {}
    stocks_per_row = 4
    current_row_frame = None

    for i, stock_info in enumerate(stocks_for_plan_generation_data):
        if i % stocks_per_row == 0:
            current_row_frame = ttk.Frame(stocks_outer_frame)
            current_row_frame.pack(fill=X, anchor=W)

        stock_name = stock_info[0]
        var = ttk.BooleanVar(value=False)
        chk = ttk.Checkbutton(current_row_frame, text=stock_name, variable=var)
        chk.pack(side=LEFT, anchor=W, pady=2, padx=5)
        selected_stocks_vars[stock_name] = var

    plan_type_frame = ttk.Frame(main_frame)
    plan_type_frame.pack(fill=X, pady=(10, 5))
    ttk.Label(plan_type_frame, text="Select Plan Type:", font=("Helvetica", 10)).pack(side=LEFT, padx=(0, 5))
    plan_type_var = ttk.StringVar(value=initial_plan_type)
    plan_type_combo = ttk.Combobox(plan_type_frame, textvariable=plan_type_var, values=["Swing Trader", "Day Trader"], state="readonly")
    plan_type_combo.pack(side=LEFT, fill=X, expand=True)

    if plan_type_disabled:
        plan_type_combo.config(state=DISABLED)

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=X, pady=(10, 0))

    generate_plan_button = ttk.Button(button_frame, text="Generate Plan", state=DISABLED, bootstyle="success")
    generate_plan_button.pack(side=RIGHT)

    def update_generate_button_state(*args):
        if any(var.get() for var in selected_stocks_vars.values()):
            generate_plan_button.config(state=NORMAL)
        else:
            generate_plan_button.config(state=DISABLED)

    for var in selected_stocks_vars.values():
        var.trace_add("write", update_generate_button_state)
    
    update_generate_button_state()

    def generate_plan_for_selected_action():
        selected_stock_details_for_plan = []
        for stock_data_item in stocks_for_plan_generation_data:
            stock_name = stock_data_item[0]
            if selected_stocks_vars.get(stock_name) and selected_stocks_vars[stock_name].get():
                selected_stock_details_for_plan.append(stock_data_item)
        
        if not selected_stock_details_for_plan:
            simpledialog.messagebox.showwarning("No Selection", "Please select at least one stock to generate a plan.", parent=plan_window)
            return

        selected_plan_type = plan_type_var.get()
        generated_plans = generate_plans_for_stocks(selected_stock_details_for_plan, plan_type=selected_plan_type)
        
        show_generated_plans_window(plan_window.master, generated_plans, plan_window)

    generate_plan_button.config(command=generate_plan_for_selected_action)

# --- Stock Screener/Filter Window (Generator Window) ---
def open_generator_window():
    """Open a new window for the generator"""
    generator_window = ttk.Toplevel(title="Stocks Filter System")

    main_gen_frame = ttk.Frame(generator_window, padding=10)
    main_gen_frame.pack(fill=BOTH, expand=True)

    filters_panel_frame = ttk.Frame(main_gen_frame)
    filters_panel_frame.pack(fill=X, pady=(0, 10))
    ttk.Label(filters_panel_frame, text="Select Filter Options:", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0,5))
    filter_manager = FilterManager(filters_panel_frame)

    shared_detected_stocks_list = []
    plan_type_config = {"type": "Swing Trader", "disabled": False}

    def set_plan_type_config_callback(plan_type_from_detection, disable_selection_from_detection):
        plan_type_config["type"] = plan_type_from_detection if plan_type_from_detection else "Swing Trader"
        plan_type_config["disabled"] = disable_selection_from_detection

    results_display_frame = ttk.Frame(main_gen_frame)
    results_display_frame.pack(fill=BOTH, expand=True, pady=(0, 10))
    result_text = ttk.Text(results_display_frame, wrap=WORD, height=10)
    result_text.pack(fill=BOTH, expand=True, side=LEFT)
    scrollbar = ttk.Scrollbar(results_display_frame, command=result_text.yview)
    scrollbar.pack(fill=Y, side=RIGHT)
    result_text.config(yscrollcommand=scrollbar.set)

    action_buttons_frame = ttk.Frame(main_gen_frame)
    action_buttons_frame.pack(fill=X, pady=(10,0))
    
    continue_button = ttk.Button(
        action_buttons_frame,
        text="Continue to Plan Setup",
        bootstyle="info",
        state=DISABLED,
        command=lambda: open_trading_plan_window(
            parent_window=generator_window.master, 
            stocks_for_plan_generation_data=shared_detected_stocks_list,
            initial_plan_type=plan_type_config["type"],
            plan_type_disabled=plan_type_config["disabled"],
            original_screener_window=None
        )
    )

    def progress_callback_impl(message):
        if result_text.winfo_exists():
            root.after(0, lambda: (
                result_text.insert(END, message + "\n"),
                result_text.see(END)
            ))

    def completion_callback_impl(detected_stocks_summary_data, summary_text, final_status):
        if result_text.winfo_exists():
            root.after(0, lambda: (
                result_text.delete(1.0, END),
                result_text.insert(END, summary_text),
                result_text.insert(END, final_status),
                result_text.see(END)
            ))

    def set_continue_button_state_impl(enable):
        if continue_button.winfo_exists():
            root.after(0, lambda: continue_button.config(state=NORMAL if enable else DISABLED))

    def post_detection_callback_impl(detected_stocks_summary_data, summary_text, final_status, trend_line_confirmation_needed):
        if trend_line_confirmation_needed:
            open_trend_line_confirmation_window(
                generator_window, 
                detected_stocks_summary_data, 
                summary_text, 
                final_status, 
                completion_callback_impl, 
                set_continue_button_state_impl, 
                shared_detected_stocks_list
            )
        else:
            completion_callback_impl(detected_stocks_summary_data, summary_text, final_status)
            if detected_stocks_summary_data:
                set_continue_button_state_impl(True)
            else:
                set_continue_button_state_impl(False)

    def on_run_detection():
        if filter_manager.is_valid_selection():
            selected_filters = filter_manager.get_selected_filters()
            trend_line_confirmation_selected = selected_filters.get("trend_line_confirmation", False)
            
            if result_text.winfo_exists():
                result_text.delete(1.0, END)
            set_continue_button_state_impl(False)
            shared_detected_stocks_list.clear()

            threading.Thread(
                target=detect_break_high_price,
                args=(
                    selected_filters,
                    shared_detected_stocks_list, 
                    progress_callback_impl,
                    post_detection_callback_impl, 
                    set_plan_type_config_callback,
                    trend_line_confirmation_selected
                ),
                daemon=True
            ).start()
        else:
            progress_callback_impl("Error: At least one Break High Price filter must be selected.")

    run_button = ttk.Button(
        action_buttons_frame, 
        text="Run Detection", 
        bootstyle="success",
        command=on_run_detection
    )
    run_button.pack(side=LEFT, padx=5)
    continue_button.pack(side=LEFT, padx=5)

    center_toplevel_window(generator_window) # Call after all widgets are packed

# --- Main Application Page ---
def show_main_page():
    global main_plan_display_treeview
    for widget in center_frame.winfo_children():
        widget.destroy()
    
    center_frame.pack_forget()
    center_frame.place_forget()
    
    main_frame = ttk.Frame(root)
    main_frame.pack(expand=True, fill=BOTH, padx=20, pady=20)
    
    header_frame = ttk.Frame(main_frame)
    header_frame.pack(fill=X, pady=(0, 20))
    
    header_title = ttk.Label(header_frame, text="Trading Plan Generator", font=("Helvetica", 14, "bold"))
    header_title.pack(side=LEFT)

    # Sidebar Frame
    sidebar_frame = ttk.Frame(main_frame, width=150)
    sidebar_frame.pack(side=LEFT, fill=Y, padx=(0, 10), pady=(0,10))

    create_button = ttk.Button(sidebar_frame, text="Create", bootstyle="primary", command=open_generator_window)
    create_button.pack(pady=5, fill=X)

    manage_plans_button = ttk.Button(sidebar_frame, text="Manage Plans", bootstyle="info", command=lambda: open_manage_plans_window(root))
    manage_plans_button.pack(pady=5, fill=X)

    delete_plans_button = ttk.Button(sidebar_frame, text="Delete All Plans", bootstyle="danger", command=delete_all_saved_plans)
    delete_plans_button.pack(pady=5, fill=X)

    main_page_display_frame = ttk.Frame(main_frame, padding=(0, 10))
    main_page_display_frame.pack(side=LEFT, fill=BOTH, expand=True)

    ttk.Label(main_page_display_frame, text="Saved Trading Plans:", font=("Helvetica", 10, "italic")).pack(anchor=W, pady=(5,5))
    
    plan_columns = ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3", "creation_date")
    main_plan_display_treeview = ttk.Treeview(main_page_display_frame, columns=plan_columns, show="headings", height=10)
    
    main_plan_display_treeview.heading("stock", text="Stock")
    main_plan_display_treeview.heading("entry_price", text="Entry")
    main_plan_display_treeview.heading("stop_loss", text="Stop Loss")
    main_plan_display_treeview.heading("tp1", text="TP1")
    main_plan_display_treeview.heading("tp2", text="TP2")
    main_plan_display_treeview.heading("tp3", text="TP3")
    main_plan_display_treeview.heading("creation_date", text="Date Created")

    main_plan_display_treeview.column("stock", width=80, anchor=CENTER)
    main_plan_display_treeview.column("entry_price", width=90, anchor=CENTER)
    main_plan_display_treeview.column("stop_loss", width=90, anchor=CENTER)
    main_plan_display_treeview.column("tp1", width=90, anchor=CENTER)
    main_plan_display_treeview.column("tp2", width=90, anchor=CENTER)
    main_plan_display_treeview.column("tp3", width=90, anchor=CENTER)
    main_plan_display_treeview.column("creation_date", width=120, anchor=CENTER)

    main_plan_display_treeview.pack(fill=BOTH, expand=True, side=LEFT)
    
    scrollbar_main_display = ttk.Scrollbar(main_page_display_frame, command=main_plan_display_treeview.yview)
    scrollbar_main_display.pack(fill=Y, side=RIGHT)
    main_plan_display_treeview.config(yscrollcommand=scrollbar_main_display.set)

    loaded_plans = load_plans_from_file()
    display_plans_in_main_area_placeholder(loaded_plans, main_plan_display_treeview)

# --- Manage Saved Plans Window ---
def open_manage_plans_window(parent_window):
    manage_window = ttk.Toplevel(parent_window)
    manage_window.title("Manage Saved Trading Plans")
    manage_window.transient(parent_window)
    manage_window.grab_set()
    center_toplevel_window(manage_window)

    main_manage_frame = ttk.Frame(manage_window, padding=10)
    main_manage_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_manage_frame, text="Select plans to delete:", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0,10))
    
    cols = ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3", "creation_date")
    tree_manage = ttk.Treeview(main_manage_frame, columns=cols, show="headings", height=15)

    tree_manage.heading("stock", text="Stock")
    tree_manage.heading("entry_price", text="Entry")
    tree_manage.heading("stop_loss", text="SL")
    tree_manage.heading("tp1", text="TP1")
    tree_manage.heading("tp2", text="TP2")
    tree_manage.heading("tp3", text="TP3")
    tree_manage.heading("creation_date", text="Date Created")

    tree_manage.column("stock", width=80, anchor=CENTER)
    tree_manage.column("entry_price", width=90, anchor=CENTER)
    tree_manage.column("stop_loss", width=90, anchor=CENTER)
    tree_manage.column("tp1", width=90, anchor=CENTER)
    tree_manage.column("tp2", width=90, anchor=CENTER)
    tree_manage.column("tp3", width=90, anchor=CENTER)
    tree_manage.column("creation_date", width=120, anchor=CENTER)

    tree_manage.pack(fill=BOTH, expand=True, pady=5)
    
    scrollbar_manage_tree = ttk.Scrollbar(main_manage_frame, orient=VERTICAL, command=tree_manage.yview)
    tree_manage.configure(yscrollcommand=scrollbar_manage_tree.set)
    scrollbar_manage_tree.pack(side=RIGHT, fill=Y, before=tree_manage)

    def populate_manage_plans_tree():
        for item in tree_manage.get_children():
            tree_manage.delete(item)

        current_plans = load_plans_from_file()
        if not current_plans:
            tree_manage.insert("", END, values=("No plans saved.", "", "", "", "", "", ""))
            return

        for i, plan_data in enumerate(current_plans):
            stock = plan_data.get("stock", "N/A")
            entry = plan_data.get("entry_price", "N/A")
            sl = plan_data.get("stop_loss", "N/A")
            tp1 = plan_data.get("tp1", "N/A")
            tp2 = plan_data.get("tp2", "N/A")
            tp3 = plan_data.get("tp3", "N/A")
            creation_date = plan_data.get("creation_date", "N/A")
            
            item_id = tree_manage.insert("", END, values=(stock, entry, sl, tp1, tp2, tp3, creation_date), tags=(stock,))

    populate_manage_plans_tree()
    tree_manage.config(selectmode="extended")

    button_manage_frame = ttk.Frame(main_manage_frame)
    button_manage_frame.pack(fill=X, pady=(10, 0))

    def delete_selected_action():
        selected_item_ids = tree_manage.selection()
        if not selected_item_ids:
            simpledialog.messagebox.showwarning("No Selection", "Please select at least one plan to delete.", parent=manage_window)
            return

        stocks_to_delete = set()
        for item_id in selected_item_ids:
            item_values = tree_manage.item(item_id, "values")
            if item_values and len(item_values) > 0:
                stock_name = item_values[0]
                if stock_name != "No plans saved.":
                    stocks_to_delete.add(stock_name)
            
        if not stocks_to_delete:
            simpledialog.messagebox.showerror("Error", "Could not identify stocks to delete from selection.", parent=manage_window)
            return

        confirm = simpledialog.messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete {len(stocks_to_delete)} selected plan(s)? This action cannot be undone.",
            parent=manage_window
        )

        if confirm:
            current_plans = load_plans_from_file()
            plans_to_keep = [plan for plan in current_plans if plan.get("stock") not in stocks_to_delete]
            
            try:
                with open(SAVED_PLANS_FILE, "w") as f:
                    json.dump(plans_to_keep, f, indent=4)
                simpledialog.messagebox.showinfo("Success", f"{len(stocks_to_delete)} plan(s) deleted successfully.", parent=manage_window)
                
                populate_manage_plans_tree()
                if main_plan_display_treeview:
                    display_plans_in_main_area_placeholder(plans_to_keep, main_plan_display_treeview)
            
            except IOError as e:
                simpledialog.messagebox.showerror("Save Error", f"Could not update plans file: {e}", parent=manage_window)
        else:
            simpledialog.messagebox.showinfo("Cancelled", "Delete operation cancelled.", parent=manage_window)

    close_button = ttk.Button(button_manage_frame, text="Close", command=manage_window.destroy, bootstyle="secondary")
    close_button.pack(side=LEFT, padx=5)

    delete_selected_button = ttk.Button(button_manage_frame, text="Delete Selected", command=delete_selected_action, bootstyle="danger")
    delete_selected_button.pack(side=RIGHT, padx=5)

# --- API Availability Check ---
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

# --- Application Start ---
root.after(100, start_api_check)
root.mainloop()