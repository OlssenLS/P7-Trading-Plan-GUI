import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import requests
import os
import pandas as pd
from datetime import datetime
import json
from tkinter import simpledialog # For asking risk percentage

# Import from the new module
from breakHighPriceDetection import detect_break_high_price, DATA_DIR, STOCKS_FILE, get_stock_list
from autoGenerateTradingPlan import generate_plans_for_stocks, display_plans_in_main_area_placeholder # Import new functions

# Get the script directory for file paths - This SCRIPT_DIR is for main.py specific paths if any.
# The breakHighPriceDetection module manages its own SCRIPT_DIR for its file operations.
# SCRIPT_DIR_MAIN = os.path.dirname(os.path.abspath(__file__)) # Keep if main.py has other file needs

# Define the path for saved trading plans
SAVED_PLANS_FILE = os.path.join(DATA_DIR, "saved_trading_plans.json")

root = ttk.Window(themename="darkly")
root.title("Trading Plan Generator")
root.geometry("1200x600")
root.resizable(True, True)

center_frame = ttk.Frame(root)
center_frame.pack(expand=True, fill=BOTH)
center_frame.place(relx=0.5, rely=0.5, anchor=CENTER)

# --- API check ---
api_status_label = ttk.Label(center_frame, text="Checking API availability...")
api_status_label.grid(column=0, row=1, padx=10, pady=10)
spinner = ttk.Progressbar(center_frame, orient=HORIZONTAL, length=300, mode="indeterminate")
spinner.grid(column=0, row=0, padx=10, pady=10)
spinner.start()

# Constants for break tracking are now in breakHighPriceDetection.py
# DATA_DIR, STOCKS_FILE are imported. DETECTION_HISTORY_FILE is managed by the module.
# KEEP_..._DAYS constants are managed by the module.

# Ensure data directory exists (using imported DATA_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

# Create default stocks.txt if it doesn't exist (using imported STOCKS_FILE)
if not os.path.exists(STOCKS_FILE):
    default_stocks = [
        "BBCA", "BBRI", "BMRI", "TLKM", "ASII", 
        "UNVR", "INDF", "ICBP", "SMGR", "CPIN"
    ]
    with open(STOCKS_FILE, "w") as f:
        f.write("\n".join(default_stocks))

# Main Treeview for displaying saved plans
main_plan_display_treeview = None # Will be assigned in show_main_page

# --- Functions for loading and saving plans ---
def load_plans_from_file():
    """Loads trading plans from the JSON file."""
    if not os.path.exists(SAVED_PLANS_FILE):
        return []
    try:
        with open(SAVED_PLANS_FILE, "r") as f:
            plans = json.load(f)
            # Ensure it's a list and handle empty file case gracefully
            return plans if isinstance(plans, list) else []
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading plans from {SAVED_PLANS_FILE}: {e}")
        # Optionally inform user, but for now, just return empty list
        # simpledialog.messagebox.showwarning("Load Error", f"Could not load plans: {e}\\nStarting with no saved plans.", parent=root)
        # To prevent data loss on next save if file was corrupt, could rename/backup here
        return []

def save_plans_to_file(new_plans_to_add):
    """Saves a list of new plans to the JSON file, updating existing or appending new."""
    existing_plans_list = load_plans_from_file()
    
    # For easier update, convert list of plans to a dict keyed by stock
    updated_plans_dict = {plan['stock']: plan for plan in existing_plans_list if 'stock' in plan}
    
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    for new_plan in new_plans_to_add:
        if 'stock' in new_plan:
            stock_key = new_plan['stock']
            if stock_key in updated_plans_dict:
                # If plan exists, update it but preserve original creation_date if it exists
                existing_plan = updated_plans_dict[stock_key]
                new_plan['creation_date'] = existing_plan.get('creation_date', current_time_str)
                updated_plans_dict[stock_key] = new_plan 
            else:
                # New plan, add creation_date
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
            # Refresh the display by showing an empty list
            if main_plan_display_treeview:
                display_plans_in_main_area_placeholder([], main_plan_display_treeview)
        except OSError as e:
            simpledialog.messagebox.showerror("Error", f"Could not delete saved plans file: {e}", parent=root)
    else:
        simpledialog.messagebox.showinfo("Cancelled", "Delete operation cancelled.", parent=root)

def show_generated_plans_window(parent_window, generated_plans, original_plan_window):
    """Open a new window to display generated trading plans and offer save/discard options."""
    if not generated_plans:
        simpledialog.messagebox.showinfo("No Plans", "No trading plans were generated.", parent=parent_window)
        return

    gen_plans_window = ttk.Toplevel(parent_window)
    gen_plans_window.title("Generated Trading Plans")
    gen_plans_window.geometry("700x500") # Adjusted size for better table display
    gen_plans_window.transient(parent_window)
    gen_plans_window.grab_set() # Make it modal

    # Main frame for the generated plans window
    main_gen_frame = ttk.Frame(gen_plans_window, padding=10)
    main_gen_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_gen_frame, text="Generated Trading Plans:", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0,10))

    # Use a Treeview for a tabular display
    columns = ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3", "rr_tp1")
    tree = ttk.Treeview(main_gen_frame, columns=columns, show="headings", height=10)
    
    # Define headings
    tree.heading("stock", text="Stock")
    tree.heading("entry_price", text="Entry Price")
    tree.heading("stop_loss", text="Stop Loss")
    tree.heading("tp1", text="TP1")
    tree.heading("tp2", text="TP2")
    tree.heading("tp3", text="TP3")
    tree.heading("rr_tp1", text="RR (TP1)")

    # Adjust column widths
    tree.column("stock", width=80, anchor=CENTER)
    tree.column("entry_price", width=100, anchor=CENTER)
    tree.column("stop_loss", width=100, anchor=CENTER)
    tree.column("tp1", width=100, anchor=CENTER)
    tree.column("tp2", width=100, anchor=CENTER)
    tree.column("tp3", width=100, anchor=CENTER)
    tree.column("rr_tp1", width=80, anchor=CENTER)

    # Insert data
    for plan in generated_plans:
        tree.insert("", END, values=([plan.get(col, "N/A") for col in columns]))

    tree.pack(fill=BOTH, expand=True, pady=5)

    # Add a scrollbar for the treeview
    scrollbar_tree = ttk.Scrollbar(main_gen_frame, orient=VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar_tree.set)
    # tree.pack(side=LEFT, fill=BOTH, expand=True) # Already packed above
    # scrollbar_tree.pack(side=RIGHT, fill=Y) # Pack it next to the tree if needed, but tree.pack with expand usually handles this

    # Button frame
    button_gen_frame = ttk.Frame(main_gen_frame)
    button_gen_frame.pack(fill=X, pady=(10, 0))

    def discard_action():
        gen_plans_window.destroy()

    def save_action():
        global main_plan_display_treeview # Use the new global variable name
        print("Saving generated plans...") 
        
        if save_plans_to_file(generated_plans): # Call the new save function
            simpledialog.messagebox.showinfo("Plans Saved", "Trading plans have been successfully saved.", parent=gen_plans_window)
            # Refresh the main page display by loading all plans (including newly saved)
            if main_plan_display_treeview:
                all_saved_plans = load_plans_from_file() 
                display_plans_in_main_area_placeholder(all_saved_plans, main_plan_display_treeview)
            else:
                print("main_plan_display_treeview not initialized. Cannot refresh display.")
        # else: # Error message is now shown by save_plans_to_file
            # simpledialog.messagebox.showwarning("Save Error", "Could not save plans to file.", parent=gen_plans_window)
            
        gen_plans_window.destroy()
        # Close the original plan_window as well (already handled below)

    discard_button = ttk.Button(button_gen_frame, text="Discard Plans", command=discard_action, bootstyle="danger")
    discard_button.pack(side=LEFT, padx=5)

    save_button = ttk.Button(button_gen_frame, text="Save & Display Plans", command=save_action, bootstyle="success")
    save_button.pack(side=RIGHT, padx=5)

    # Close the original plan_window after this new window is set up
    if original_plan_window and original_plan_window.winfo_exists():
        original_plan_window.destroy()

def open_trading_plan_window(parent_window, stocks_for_plan_generation_data, original_screener_window=None):
    """Open a new window to select stocks for trading plan generation."""
    # Close the screener window if it exists and is passed
    if original_screener_window and original_screener_window.winfo_exists():
        original_screener_window.destroy()

    plan_window = ttk.Toplevel(parent_window)
    plan_window.title("Generate Trading Plan")
    plan_window.geometry("400x500")
    plan_window.transient(parent_window) # Make it appear on top of its parent
    plan_window.grab_set() # Make it modal

    if not stocks_for_plan_generation_data:
        ttk.Label(plan_window, text="No stocks available or selected from screener for plan generation.", padding=20).pack()
        # Add a button to close this window if no stocks
        ttk.Button(plan_window, text="Close", command=plan_window.destroy).pack(pady=10)
        return

    main_frame = ttk.Frame(plan_window, padding=10)
    main_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_frame, text="Select stocks to generate trading plan for:", font=("Helvetica", 10, "bold")).pack(anchor=W, pady=(0, 10))

    stocks_frame = ttk.Frame(main_frame)
    stocks_frame.pack(fill=BOTH, expand=True, pady=5)
    
    selected_stocks_vars = {} # Store {stock_name: BooleanVar}

    for stock_info in stocks_for_plan_generation_data:
        stock_name = stock_info[0]
        var = ttk.BooleanVar(value=False) # Default to False, user must select
        # Task 1: Add a little spacing (pady) between checkboxes
        chk = ttk.Checkbutton(stocks_frame, text=stock_name, variable=var)
        chk.pack(anchor=W, pady=2) # Added pady=2 for spacing
        selected_stocks_vars[stock_name] = var

    # Plan Type Selection
    plan_type_frame = ttk.Frame(main_frame)
    plan_type_frame.pack(fill=X, pady=(10, 5))
    ttk.Label(plan_type_frame, text="Select Plan Type:", font=("Helvetica", 10)).pack(side=LEFT, padx=(0, 5))
    plan_type_var = ttk.StringVar(value="Swing Trader") # Default value
    plan_type_combo = ttk.Combobox(plan_type_frame, textvariable=plan_type_var, values=["Swing Trader", "Day Trader"], state="readonly")
    plan_type_combo.pack(side=LEFT, fill=X, expand=True)

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
    
    update_generate_button_state() # Initial check

    def generate_plan_for_selected_action():
        # Task 2: After the Generate Plan button is clicked...
        selected_stock_details_for_plan = []
        for stock_data_item in stocks_for_plan_generation_data: # use the passed list
            stock_name = stock_data_item[0]
            if selected_stocks_vars.get(stock_name) and selected_stocks_vars[stock_name].get():
                selected_stock_details_for_plan.append(stock_data_item)
        
        if not selected_stock_details_for_plan:
            simpledialog.messagebox.showwarning("No Selection", "Please select at least one stock to generate a plan.", parent=plan_window)
            return

        # Call the placeholder algorithm
        selected_plan_type = plan_type_var.get() # Get selected plan type
        generated_plans = generate_plans_for_stocks(selected_stock_details_for_plan, plan_type=selected_plan_type)
        
        # Open the new window showing generated plans
        # The original plan_window will be closed by show_generated_plans_window
        show_generated_plans_window(plan_window.master, generated_plans, plan_window) 

    generate_plan_button.config(command=generate_plan_for_selected_action)

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
        "2_months": ttk.BooleanVar(),
        "3_months": ttk.BooleanVar()
    }
    
    # Checkboxes
    ttk.Checkbutton(options_frame, text="5 Days High Price", variable=options["5_days"]).pack(anchor=W, pady=5)
    ttk.Checkbutton(options_frame, text="1 Month High Price", variable=options["1_month"]).pack(anchor=W, pady=5)
    ttk.Checkbutton(options_frame, text="2 Months High Price", variable=options["2_months"]).pack(anchor=W, pady=5)
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
    
    # Shared list for detected stocks to be passed to the trading plan window
    shared_detected_stocks_list = []

    # Continue button (initially disabled)
    continue_button = ttk.Button(
        button_frame,
        text="Continue to Plan Setup", # Renamed for clarity
        bootstyle="info",
        state=DISABLED, # Start disabled
        command=lambda: open_trading_plan_window(generator_window, shared_detected_stocks_list)
    )
    
    # Callback implementations for detect_break_high_price
    def progress_callback_impl(message):
        if result_text.winfo_exists(): # Check if widget still exists
            root.after(0, lambda: (
                result_text.insert(END, message), 
                result_text.see(END) 
                # result_text.update() # update() can be slow, see(END) is often enough
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


    # Run button
    run_button = ttk.Button(
        button_frame, 
        text="Run Detection", 
        bootstyle="success",
        command=lambda: threading.Thread(
            target=detect_break_high_price, # Use imported function
            args=(
                {k: v.get() for k, v in options.items()},
                shared_detected_stocks_list, # Pass the list to be populated
                progress_callback_impl,      # Pass the callback
                completion_callback_impl,    # Pass the callback
                set_continue_button_state_impl # Pass the callback
            ),
            daemon=True
        ).start()
    )
    run_button.pack(side=LEFT, padx=5)
    
    continue_button.pack(side=LEFT, padx=5) # Placed after Screener button

def show_main_page():
    global main_plan_display_treeview # Declare global to assign
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
    create_button.pack(side=RIGHT, padx=(5,0)) # Add some padding if it's not the last one

    # Manage Plans button
    manage_plans_button = ttk.Button(header_frame, text="Manage Plans", bootstyle="info", command=lambda: open_manage_plans_window(root)) # Added
    manage_plans_button.pack(side=RIGHT, padx=(5,5)) # Added

    # Delete All Plans button - positioned to the left of Create
    delete_plans_button = ttk.Button(header_frame, text="Delete All Plans", bootstyle="danger", command=delete_all_saved_plans)
    delete_plans_button.pack(side=RIGHT, padx=(0, 5)) # padx to add space between Delete and Create

    # Placeholder for displaying saved trading plans on the main page
    # This could be a more sophisticated widget or part of a dashboard later
    main_page_display_frame = ttk.Frame(main_frame, padding=(0, 10))
    main_page_display_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_page_display_frame, text="Saved Trading Plans:", font=("Helvetica", 10, "italic")).pack(anchor=W, pady=(5,5))
    
    # Define columns for the main display Treeview
    plan_columns = ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3", "status", "creation_date") # Updated columns
    main_plan_display_treeview = ttk.Treeview(main_page_display_frame, columns=plan_columns, show="headings", height=10)
    
    # Define headings for the Treeview
    main_plan_display_treeview.heading("stock", text="Stock")
    main_plan_display_treeview.heading("entry_price", text="Entry")
    main_plan_display_treeview.heading("stop_loss", text="Stop Loss")
    main_plan_display_treeview.heading("tp1", text="TP1")
    main_plan_display_treeview.heading("tp2", text="TP2")
    main_plan_display_treeview.heading("tp3", text="TP3")
    main_plan_display_treeview.heading("status", text="Status")
    main_plan_display_treeview.heading("creation_date", text="Date Created") # Added

    # Adjust column widths for the Treeview
    main_plan_display_treeview.column("stock", width=80, anchor=CENTER)
    main_plan_display_treeview.column("entry_price", width=90, anchor=CENTER) # Adjusted, Changed from E to CENTER
    main_plan_display_treeview.column("stop_loss", width=90, anchor=CENTER)  # Adjusted, Changed from E to CENTER
    main_plan_display_treeview.column("tp1", width=90, anchor=CENTER)       # Adjusted, Changed from E to CENTER
    main_plan_display_treeview.column("tp2", width=90, anchor=CENTER)       # Adjusted, Changed from E to CENTER
    main_plan_display_treeview.column("tp3", width=90, anchor=CENTER)       # Adjusted, Changed from E to CENTER
    main_plan_display_treeview.column("status", width=80, anchor=CENTER)
    main_plan_display_treeview.column("creation_date", width=120, anchor=CENTER) # Added

    main_plan_display_treeview.pack(fill=BOTH, expand=True, side=LEFT)
    
    scrollbar_main_display = ttk.Scrollbar(main_page_display_frame, command=main_plan_display_treeview.yview)
    scrollbar_main_display.pack(fill=Y, side=RIGHT)
    main_plan_display_treeview.config(yscrollcommand=scrollbar_main_display.set)

    # Load and display existing plans from file
    loaded_plans = load_plans_from_file()
    display_plans_in_main_area_placeholder(loaded_plans, main_plan_display_treeview)

# --- Manage Plans Window ---
def open_manage_plans_window(parent_window):
    manage_window = ttk.Toplevel(parent_window)
    manage_window.title("Manage Saved Trading Plans")
    manage_window.geometry("800x500") # Adjusted for more columns
    manage_window.transient(parent_window)
    manage_window.grab_set()

    main_manage_frame = ttk.Frame(manage_window, padding=10)
    main_manage_frame.pack(fill=BOTH, expand=True)

    ttk.Label(main_manage_frame, text="Select plans to delete:", font=("Helvetica", 12, "bold")).pack(anchor=W, pady=(0,10))

    # Treeview for displaying plans with checkboxes
    # We'll need a custom way to handle checkboxes in a treeview or use a list of checkbuttons if simpler
    # For now, let's set up the treeview structure. The actual selection mechanism will be decided.
    
    cols = ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3", "status", "creation_date") # Updated, removed "select"
    tree_manage = ttk.Treeview(main_manage_frame, columns=cols, show="headings", height=15)

    tree_manage.heading("stock", text="Stock")
    tree_manage.heading("entry_price", text="Entry")
    tree_manage.heading("stop_loss", text="SL")
    tree_manage.heading("tp1", text="TP1")
    tree_manage.heading("tp2", text="TP2")
    tree_manage.heading("tp3", text="TP3")
    tree_manage.heading("status", text="Status")
    tree_manage.heading("creation_date", text="Date Created") # Added

    # tree_manage.column("select", width=50, anchor=CENTER, stretch=False) # Removed
    tree_manage.column("stock", width=80, anchor=CENTER)
    tree_manage.column("entry_price", width=90, anchor=CENTER) # Adjusted, Changed from E to CENTER
    tree_manage.column("stop_loss", width=90, anchor=CENTER)  # Adjusted, Changed from E to CENTER
    tree_manage.column("tp1", width=90, anchor=CENTER)       # Adjusted, Changed from E to CENTER
    tree_manage.column("tp2", width=90, anchor=CENTER)       # Adjusted, Changed from E to CENTER
    tree_manage.column("tp3", width=90, anchor=CENTER)       # Adjusted, Changed from E to CENTER
    tree_manage.column("status", width=80, anchor=CENTER)
    tree_manage.column("creation_date", width=120, anchor=CENTER) # Added

    tree_manage.pack(fill=BOTH, expand=True, pady=5)
    
    scrollbar_manage_tree = ttk.Scrollbar(main_manage_frame, orient=VERTICAL, command=tree_manage.yview)
    tree_manage.configure(yscrollcommand=scrollbar_manage_tree.set)
    scrollbar_manage_tree.pack(side=RIGHT, fill=Y, before=tree_manage) # Pack before tree to avoid overlap if not careful

    def populate_manage_plans_tree():
        # Clear existing items
        for item in tree_manage.get_children():
            tree_manage.delete(item)

        current_plans = load_plans_from_file()
        if not current_plans:
            tree_manage.insert("", END, values=("No plans saved.", "", "", "", "", "", "", "")) # Adjusted for removed column
            return

        for i, plan_data in enumerate(current_plans):
            stock = plan_data.get("stock", "N/A")
            entry = plan_data.get("entry_price", "N/A")
            sl = plan_data.get("stop_loss", "N/A")
            tp1 = plan_data.get("tp1", "N/A")
            tp2 = plan_data.get("tp2", "N/A")
            tp3 = plan_data.get("tp3", "N/A")
            status = plan_data.get("status", "Pending")
            creation_date = plan_data.get("creation_date", "N/A") # Added
            
            # For selection, we'll use the treeview's built-in selection mechanism
            # and then retrieve selected items. Checkboxes in each row are complex.
            # Instead, we allow multi-selection in the treeview.
            item_id = tree_manage.insert("", END, values=(stock, entry, sl, tp1, tp2, tp3, status, creation_date), tags=(stock,)) # Adjusted for removed column
            # The first column is kept empty for now, could be used for a visual cue later if needed

    populate_manage_plans_tree()
    tree_manage.config(selectmode="extended") # Allow multiple selections

    # Button frame
    button_manage_frame = ttk.Frame(main_manage_frame)
    button_manage_frame.pack(fill=X, pady=(10, 0))

    def delete_selected_action():
        selected_item_ids = tree_manage.selection() # Get selected item IDs
        if not selected_item_ids:
            simpledialog.messagebox.showwarning("No Selection", "Please select at least one plan to delete.", parent=manage_window)
            return

        stocks_to_delete = set()
        for item_id in selected_item_ids:
            # Retrieve the stock name from the item's values or tags
            # Assuming stock name is unique and stored as a tag or in a specific column
            item_values = tree_manage.item(item_id, "values")
            if item_values and len(item_values) > 0: # Check if item_values is not empty
                 # Assuming stock is the first column (index 0) now that 'select' is removed
                stock_name = item_values[0]
                if stock_name != "No plans saved.": # Ensure it's a valid stock
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
            
            # Attempt to save the filtered list
            # We re-use save_plans_to_file by passing the complete list of plans to keep.
            # This function internally converts to dict by stock and then back to list, effectively overwriting.
            
            # To truly overwrite with a potentially smaller list using the current save_plans_to_file,
            # we must ensure it writes the provided list directly, not merge.
            # Let's adjust save_plans_to_file to handle this, or make a specific "overwrite" save.
            # For now, let's assume save_plans_to_file needs to be more flexible or we need a new one.
            # Let's create a more direct save for this purpose to avoid complexity with the existing one.
            
            try:
                with open(SAVED_PLANS_FILE, "w") as f:
                    json.dump(plans_to_keep, f, indent=4)
                simpledialog.messagebox.showinfo("Success", f"{len(stocks_to_delete)} plan(s) deleted successfully.", parent=manage_window)
                
                # Refresh displays
                populate_manage_plans_tree() # Refresh this window's tree
                if main_plan_display_treeview: # Refresh main window's tree
                    display_plans_in_main_area_placeholder(plans_to_keep, main_plan_display_treeview)
            
            except IOError as e:
                simpledialog.messagebox.showerror("Save Error", f"Could not update plans file: {e}", parent=manage_window)
        else:
            simpledialog.messagebox.showinfo("Cancelled", "Delete operation cancelled.", parent=manage_window)


    close_button = ttk.Button(button_manage_frame, text="Close", command=manage_window.destroy, bootstyle="secondary")
    close_button.pack(side=LEFT, padx=5)

    delete_selected_button = ttk.Button(button_manage_frame, text="Delete Selected", command=delete_selected_action, bootstyle="danger")
    delete_selected_button.pack(side=RIGHT, padx=5)

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