# autoGenerateTradingPlan.py
from tkinter.constants import END
from priceConversion import adjust_price_by_fraction, get_fraction_for_price, add_ticks_to_price, subtract_ticks_from_price

# --- Trading Plan Generation Logic ---
def generate_plans_for_stocks(selected_stocks_details, plan_type="Swing Trader", advanced_settings=None):
    """
    Generates trading plans based on detected stock breaks.
    
    Args:
        selected_stocks_details: A list of tuples for selected stocks.
        plan_type (str): "Day Trader" or "Swing Trader".
        advanced_settings (dict, optional): Dictionary with advanced parameters like ema_short, 
                                            ema_long, entry_offset, sl_offset, tp1_rr, tp2_rr, tp3_rr.

    Returns:
        A list of generated plan dictionaries.
    """
    generated_plans = []
    if not selected_stocks_details:
        return []

    for stock_detail in selected_stocks_details:
        stock_name, reasons, latest_close, latest_low_of_day, latest_high_of_day, period_high_prices_info, potential_tp_levels_from_history = stock_detail 
        
        # Initialize defaults
        entry_price_actual = None
        stop_loss_val_adj = None
        tp1_val_adj, tp2_val_adj, tp3_val_adj = None, None, None
        entry_price_str = "N/A" # Initialize entry_price_str

        adj_latest_low = adjust_price_by_fraction(latest_low_of_day)
        adj_latest_high = adjust_price_by_fraction(latest_high_of_day)
        adj_latest_close = adjust_price_by_fraction(latest_close)

        if advanced_settings:
            # Determine Entry Price String and Actual Entry for SL/TP calcs
            entry_type = advanced_settings.get("entry_range_type", "Low to High")
            if entry_type == "Low to High":
                entry_price_str = f"{adj_latest_low} - {adj_latest_high}"
                entry_price_actual = float(adj_latest_high) # For long, worst entry is high
            elif entry_type == "Low to Close":
                entry_price_str = f"{adj_latest_low} - {adj_latest_close}"
                entry_price_actual = float(adj_latest_close) # For long, worst entry is close if high not included
            elif entry_type == "Close to High":
                entry_price_str = f"{adj_latest_close} - {adj_latest_high}"
                entry_price_actual = float(adj_latest_high) # For long, worst entry is high
            else: # Fallback or error
                entry_price_str = f"{adj_latest_low} - {adj_latest_high}" # Default to Low to High
                entry_price_actual = float(adj_latest_high)

            # Calculate Stop Loss
            sl_def_type = advanced_settings.get("sl_definition_type", "Percentage")
            sl_value = advanced_settings.get("sl_value", 2) # Default 2% or 2 ticks

            if sl_def_type == "Percentage":
                stop_loss_val_raw = entry_price_actual * (1 - (sl_value / 100.0))
                stop_loss_val_adj = adjust_price_by_fraction(stop_loss_val_raw)
            elif sl_def_type == "Ticks":
                stop_loss_val_adj = subtract_ticks_from_price(entry_price_actual, int(sl_value))
            else: # Fallback to percentage
                stop_loss_val_raw = entry_price_actual * (1 - (sl_value / 100.0))
                stop_loss_val_adj = adjust_price_by_fraction(stop_loss_val_raw)
            
            if stop_loss_val_adj >= entry_price_actual: # Ensure SL is below entry for long
                print(f"Warning: Calculated SL {stop_loss_val_adj} is not below entry {entry_price_actual} for {stock_name}. Adjusting SL one tick lower or re-evaluate inputs.")
                stop_loss_val_adj = subtract_ticks_from_price(entry_price_actual, 1)
                if stop_loss_val_adj >= entry_price_actual: # If still not below, indicates issue
                     print(f"Critical Warning: SL adjustment failed for {stock_name}. Defaulting SL significantly lower or skipping plan.")
                     # Potentially skip plan or set a very conservative SL
                     stop_loss_val_adj = adjust_price_by_fraction(entry_price_actual * 0.90) # Fallback to 10% SL

            # Calculate Take Profits based on R/R
            risk_per_share = entry_price_actual - stop_loss_val_adj
            if risk_per_share <= 0:
                print(f"Warning: Risk per share is not positive for {stock_name} with advanced settings. SL: {stop_loss_val_adj}, Entry: {entry_price_actual}. Skipping TP calculation.")
                tp1_val_adj, tp2_val_adj, tp3_val_adj = None, None, None
            else:
                # TP1 Calculation
                tp1_type = advanced_settings.get("tp1_type", "Percentage")
                tp1_value = advanced_settings.get("tp1_value", 3) # Default to 3% or 3 ticks
                if tp1_type == "Percentage":
                    tp1_val_raw = entry_price_actual * (1 + (tp1_value / 100.0))
                elif tp1_type == "Ticks":
                    tp1_val_raw = add_ticks_to_price(entry_price_actual, int(tp1_value))
                else: # Fallback
                    tp1_val_raw = entry_price_actual * (1 + (tp1_value / 100.0))
                tp1_val_adj = adjust_price_by_fraction(tp1_val_raw)
                if tp1_val_adj <= entry_price_actual: tp1_val_adj = None # Ensure TP is above entry

                # TP2 Calculation
                if tp1_val_adj is not None:
                    tp2_type = advanced_settings.get("tp2_type", "Percentage")
                    tp2_value = advanced_settings.get("tp2_value", 5)
                    if tp2_type == "Percentage":
                        tp2_val_raw = entry_price_actual * (1 + (tp2_value / 100.0))
                    elif tp2_type == "Ticks":
                        tp2_val_raw = add_ticks_to_price(entry_price_actual, int(tp2_value))
                    else: # Fallback
                        tp2_val_raw = entry_price_actual * (1 + (tp2_value / 100.0))
                    tp2_val_adj = adjust_price_by_fraction(tp2_val_raw)
                    if tp2_val_adj <= tp1_val_adj: tp2_val_adj = None # Ensure TP2 > TP1
                else:
                    tp2_val_adj = None

                # TP3 Calculation
                if tp2_val_adj is not None:
                    tp3_type = advanced_settings.get("tp3_type", "Percentage")
                    tp3_value = advanced_settings.get("tp3_value", 7)
                    if tp3_type == "Percentage":
                        tp3_val_raw = entry_price_actual * (1 + (tp3_value / 100.0))
                    elif tp3_type == "Ticks":
                        tp3_val_raw = add_ticks_to_price(entry_price_actual, int(tp3_value))
                    else: # Fallback
                        tp3_val_raw = entry_price_actual * (1 + (tp3_value / 100.0))
                    tp3_val_adj = adjust_price_by_fraction(tp3_val_raw)
                    if tp3_val_adj <= tp2_val_adj: tp3_val_adj = None # Ensure TP3 > TP2
                elif tp1_val_adj is not None: # Calculate TP3 based on TP1 if TP2 is None
                    tp3_type = advanced_settings.get("tp3_type", "Percentage")
                    tp3_value = advanced_settings.get("tp3_value", 7)
                    if tp3_type == "Percentage":
                        tp3_val_raw = entry_price_actual * (1 + (tp3_value / 100.0))
                    elif tp3_type == "Ticks":
                        tp3_val_raw = add_ticks_to_price(entry_price_actual, int(tp3_value))
                    else: # Fallback
                        tp3_val_raw = entry_price_actual * (1 + (tp3_value / 100.0))
                    tp3_val_adj = adjust_price_by_fraction(tp3_val_raw)
                    if tp3_val_adj <= tp1_val_adj: tp3_val_adj = None # Ensure TP3 > TP1
                else:
                    tp3_val_adj = None

        else:
            # Original logic if no advanced settings
            adj_entry_low_orig = adjust_price_by_fraction(latest_low_of_day)
            adj_entry_high_orig = adjust_price_by_fraction(latest_high_of_day)
            entry_price_str = f"{adj_entry_low_orig} - {adj_entry_high_orig}"
            entry_price_actual = float(adj_entry_high_orig) 
            
            stop_loss_calculation_base = float(adj_entry_low_orig)
            
            if plan_type == "Day Trader":
                stop_loss_percentage = 0.99
                min_ticks_separation = 2
                min_ticks_for_tp2 = 3
                min_ticks_for_tp3 = 4
            else: # Swing Trader
                stop_loss_percentage = 0.95
                min_ticks_separation = 3
                min_ticks_for_tp2 = 5
                min_ticks_for_tp3 = 7

            stop_loss_val_raw = stop_loss_calculation_base * stop_loss_percentage
            stop_loss_val_adj = adjust_price_by_fraction(stop_loss_val_raw)

            tp_levels_raw = potential_tp_levels_from_history
            current_search_start_index = 0
            base_for_next_tp_min_target = adj_entry_high_orig

            # Find TP1
            if potential_tp_levels_from_history:
                calculated_min_target_tp1 = add_ticks_to_price(base_for_next_tp_min_target, min_ticks_separation)
                raw_tp1_found_at_index = -1

                for i in range(current_search_start_index, len(tp_levels_raw)):
                    raw_candidate = tp_levels_raw[i]
                    if raw_candidate >= calculated_min_target_tp1:
                        adjusted_candidate = adjust_price_by_fraction(raw_candidate)
                        if adjusted_candidate >= calculated_min_target_tp1: 
                            tp1_val_adj = adjusted_candidate
                            base_for_next_tp_min_target = tp1_val_adj
                            raw_tp1_found_at_index = i
                            break
                current_search_start_index = raw_tp1_found_at_index + 1 if raw_tp1_found_at_index != -1 else len(tp_levels_raw)

            # Find TP2
            if tp1_val_adj is not None and potential_tp_levels_from_history:
                calculated_min_target_tp2 = add_ticks_to_price(base_for_next_tp_min_target, min_ticks_for_tp2)
                raw_tp2_found_at_index = -1
                for i in range(current_search_start_index, len(tp_levels_raw)):
                    raw_candidate = tp_levels_raw[i]
                    if raw_candidate >= calculated_min_target_tp2:
                        adjusted_candidate = adjust_price_by_fraction(raw_candidate)
                        if adjusted_candidate > tp1_val_adj and adjusted_candidate >= calculated_min_target_tp2:
                            tp2_val_adj = adjusted_candidate
                            base_for_next_tp_min_target = tp2_val_adj
                            raw_tp2_found_at_index = i
                            break
                current_search_start_index = raw_tp2_found_at_index + 1 if raw_tp2_found_at_index != -1 else len(tp_levels_raw)

            # Find TP3
            if tp2_val_adj is not None and potential_tp_levels_from_history:
                calculated_min_target_tp3 = add_ticks_to_price(base_for_next_tp_min_target, min_ticks_for_tp3)
                for i in range(current_search_start_index, len(tp_levels_raw)):
                    raw_candidate = tp_levels_raw[i]
                    if raw_candidate >= calculated_min_target_tp3:
                        adjusted_candidate = adjust_price_by_fraction(raw_candidate)
                        if adjusted_candidate > tp2_val_adj and adjusted_candidate >= calculated_min_target_tp3:
                            tp3_val_adj = adjusted_candidate
                            break

        rr_tp1_str = "N/A" # This should be recalculated if advanced_settings are used
        if advanced_settings and entry_price_actual and stop_loss_val_adj and tp1_val_adj and (entry_price_actual - stop_loss_val_adj > 0):
            risk = entry_price_actual - stop_loss_val_adj
            reward_tp1 = tp1_val_adj - entry_price_actual
            if risk > 0 and reward_tp1 > 0: # Ensure risk and reward are positive
                 rr_tp1_str = f"{reward_tp1/risk:.2f}:1"
        elif not advanced_settings and entry_price_actual and stop_loss_val_adj and tp1_val_adj:
             # Original R/R calculation logic if not using advanced settings for TP
            try:
                risk_orig = float(entry_price_actual) - float(stop_loss_val_adj) # Assuming entry_price_actual and stop_loss_val_adj are numbers or number strings
                reward_tp1_orig = float(tp1_val_adj) - float(entry_price_actual)
                if risk_orig > 0 and reward_tp1_orig > 0:
                    rr_tp1_str = f"{reward_tp1_orig/risk_orig:.2f}:1"
            except (ValueError, TypeError):
                rr_tp1_str = "N/A" # If conversion fails

        plan = {
            "stock": stock_name,
            "reasons": ", ".join(reasons),
            "latest_close": f"{latest_close:.2f}", 
            "latest_low_of_day": f"{latest_low_of_day:.2f}",
            "latest_high_of_day": f"{latest_high_of_day:.2f}",
            "entry_price": entry_price_str,
            "stop_loss": f"{stop_loss_val_adj}",
            "tp1": f"{tp1_val_adj}" if tp1_val_adj is not None else "N/A",
            "tp2": f"{tp2_val_adj}" if tp2_val_adj is not None else "N/A",
            "tp3": f"{tp3_val_adj}" if tp3_val_adj is not None else "N/A",
            "rr_tp1": rr_tp1_str,
            "notes": f"Plan for {stock_name} based on {', '.join(reasons)}."
        }
        generated_plans.append(plan)
        
    return generated_plans

# --- Display Plans in Main UI Treeview ---
def display_plans_in_main_area_placeholder(plans, main_text_widget):
    """Displays or appends trading plans to the main UI's Treeview."""
    if main_text_widget and main_text_widget.winfo_exists():
        main_plan_treeview = main_text_widget

        for item in main_plan_treeview.get_children():
            main_plan_treeview.delete(item)

        if not plans:
            main_plan_treeview.insert("", END, values=("No plans.", "", "", "", "", "", "", ""))
            return

        for plan in plans:
            stock_name = plan.get("stock", "N/A")
            entry = plan.get("entry_price", "N/A")
            sl = plan.get("stop_loss", "N/A")
            tp1_val = plan.get("tp1", "N/A")
            tp2_val = plan.get("tp2", "N/A") 
            tp3_val = plan.get("tp3", "N/A") 
            status_val = plan.get("status", "Pending") 
            creation_date_val = plan.get("creation_date", "N/A")
            
            main_plan_treeview.insert("", END, values=(stock_name, entry, sl, tp1_val, tp2_val, tp3_val, status_val, creation_date_val))
        
    else:
        print("Main Treeview widget not available for displaying saved plans.") 