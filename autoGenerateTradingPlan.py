# autoGenerateTradingPlan.py
from tkinter.constants import END # Import necessary constants
from priceConversion import adjust_price_by_fraction # Import the new function

def generate_plans_for_stocks(selected_stocks_details):
    """
    Generates trading plans based on detected stock breaks.
    
    Args:
        selected_stocks_details: A list of tuples, where each tuple contains 
                                 (stock_name, reasons, latest_close, latest_low_of_day, latest_high_of_day, 
                                  period_high_prices_info, potential_tp_levels_from_history)
                                 for the stocks selected by the user.
                                 period_high_prices_info is a dict like {'5d': 123.45, '1m': 125.00}
                                 potential_tp_levels_from_history is a sorted list of floats.

    Returns:
        A list of generated plan objects/dictionaries.
    """
    generated_plans = []
    if not selected_stocks_details:
        print("autoGenerateTradingPlan.py: No stocks selected for plan generation.")
        return []

    print(f"autoGenerateTradingPlan.py: Received {len(selected_stocks_details)} stocks for plan generation.")

    for stock_detail in selected_stocks_details:
        stock_name, reasons, latest_close, latest_low_of_day, latest_high_of_day, period_high_prices_info, potential_tp_levels_from_history = stock_detail 
        
        # DEBUG: Log input values for TP calculation
        print(f"[DEBUG] Processing {stock_name}: Raw Entry range {latest_low_of_day:.2f}-{latest_high_of_day:.2f}")
        if potential_tp_levels_from_history:
            print(f"[DEBUG] {stock_name}: Received {len(potential_tp_levels_from_history)} potential TP levels: {[f'{tp:.2f}' for tp in potential_tp_levels_from_history]}")
        else:
            print(f"[DEBUG] {stock_name}: No potential TP levels received from historical data")
            
        # Adjust the low and high for the entry price range
        adjusted_entry_low = adjust_price_by_fraction(latest_low_of_day)
        adjusted_entry_high = adjust_price_by_fraction(latest_high_of_day)
        entry_price_str = f"{adjusted_entry_low} - {adjusted_entry_high}"
        print(f"[DEBUG] {stock_name}: Adjusted Entry Price Range: {entry_price_str}")
        
        # Use the lower end of the adjusted entry price range for stop-loss calculation
        # Ensure adjusted_entry_low is treated as a float for the calculation
        stop_loss_calculation_base = float(adjusted_entry_low)
        
        # Calculate and adjust stop loss
        stop_loss_val_raw = stop_loss_calculation_base * 0.95  # Example: 2% stop loss from adjusted_entry_low
        stop_loss_val_adj = adjust_price_by_fraction(stop_loss_val_raw)

        # New TP logic using potential_tp_levels_from_history, then adjust them
        tp1_val_adj, tp2_val_adj, tp3_val_adj = None, None, None

        if potential_tp_levels_from_history:
            if len(potential_tp_levels_from_history) > 0:
                tp1_val_raw = potential_tp_levels_from_history[0]
                tp1_val_adj = adjust_price_by_fraction(tp1_val_raw)
                print(f"[DEBUG] {stock_name}: Setting TP1 = {tp1_val_raw:.2f}, Adjusted TP1 = {tp1_val_adj}")
            if len(potential_tp_levels_from_history) > 1:
                tp2_val_raw = potential_tp_levels_from_history[1]
                tp2_val_adj = adjust_price_by_fraction(tp2_val_raw)
                print(f"[DEBUG] {stock_name}: Setting TP2 = {tp2_val_raw:.2f}, Adjusted TP2 = {tp2_val_adj}")
            if len(potential_tp_levels_from_history) > 2:
                tp3_val_raw = potential_tp_levels_from_history[2]
                tp3_val_adj = adjust_price_by_fraction(tp3_val_raw)
                print(f"[DEBUG] {stock_name}: Setting TP3 = {tp3_val_raw:.2f}, Adjusted TP3 = {tp3_val_adj}")
        else:
            print(f"[DEBUG] {stock_name}: No TP levels can be set - will use N/A")
        
        rr_tp1_str = "N/A" 
        
        plan = {
            "stock": stock_name,
            "reasons": ", ".join(reasons),
            "latest_close": f"{latest_close:.2f}", 
            "latest_low_of_day": f"{latest_low_of_day:.2f}",
            "latest_high_of_day": f"{latest_high_of_day:.2f}",
            "entry_price": entry_price_str, # Use adjusted range string
            "stop_loss": f"{stop_loss_val_adj}",     # Use adjusted integer value, formatted as string
            "tp1": f"{tp1_val_adj}" if tp1_val_adj is not None else "N/A",
            "tp2": f"{tp2_val_adj}" if tp2_val_adj is not None else "N/A",
            "tp3": f"{tp3_val_adj}" if tp3_val_adj is not None else "N/A",
            "rr_tp1": rr_tp1_str,
            "notes": f"Plan for {stock_name} based on { ', '.join(reasons) }."
        }
        generated_plans.append(plan)
        print(f"autoGenerateTradingPlan.py: Generated plan for {stock_name} with TPs: {plan['tp1']}, {plan['tp2']}, {plan['tp3']}")
        
    return generated_plans

def display_plans_in_main_area_placeholder(plans, main_text_widget):
    """
    Placeholder to demonstrate how plans might be displayed or appended to a main text area.
    In a real app, this would format and show the plans in the main UI.
    """
    if main_text_widget and main_text_widget.winfo_exists():
        main_plan_treeview = main_text_widget # Passed widget is now a Treeview

        # Clear existing items in the treeview before adding new ones
        for item in main_plan_treeview.get_children():
            main_plan_treeview.delete(item)

        if not plans:
            # Optional: Insert a placeholder if no plans are being added, 
            # or rely on the Treeview being empty.
            # For now, let's assume an empty tree is fine, or main.py handles initial placeholder.
            main_plan_treeview.insert("", END, values=("No plans to display.", "", "", "", "", "", "", "")) # Adjusted for new columns
            print("autoGenerateTradingPlan.py: No plans to display in Treeview.")
            return

        for plan in plans:
            # Ensure the values correspond to the columns defined in main.py for main_plan_display_treeview
            # Current columns in main.py: ("stock", "entry_price", "stop_loss", "tp1", "tp2", "tp3", "status", "creation_date")
            stock_name = plan.get("stock", "N/A")
            entry = plan.get("entry_price", "N/A")
            sl = plan.get("stop_loss", "N/A")
            tp1_val = plan.get("tp1", "N/A")
            tp2_val = plan.get("tp2", "N/A") 
            tp3_val = plan.get("tp3", "N/A") 
            status_val = plan.get("status", "Pending") 
            creation_date_val = plan.get("creation_date", "N/A") # Added
            
            main_plan_treeview.insert("", END, values=(stock_name, entry, sl, tp1_val, tp2_val, tp3_val, status_val, creation_date_val))
        
    else:
        print("Main Treeview widget not available for displaying saved plans.")
    print("autoGenerateTradingPlan.py: Updated placeholder for displaying plans in Treeview.") 