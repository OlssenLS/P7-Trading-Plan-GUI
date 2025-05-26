# autoGenerateTradingPlan.py
from tkinter.constants import END
from priceConversion import adjust_price_by_fraction, get_fraction_for_price, add_ticks_to_price

# --- Trading Plan Generation Logic ---
def generate_plans_for_stocks(selected_stocks_details, plan_type="Swing Trader"):
    """
    Generates trading plans based on detected stock breaks.
    
    Args:
        selected_stocks_details: A list of tuples for selected stocks.
        plan_type (str): "Day Trader" or "Swing Trader".

    Returns:
        A list of generated plan dictionaries.
    """
    generated_plans = []
    if not selected_stocks_details:
        return []

    for stock_detail in selected_stocks_details:
        stock_name, reasons, latest_close, latest_low_of_day, latest_high_of_day, period_high_prices_info, potential_tp_levels_from_history = stock_detail 
        
        adjusted_entry_low = adjust_price_by_fraction(latest_low_of_day)
        adjusted_entry_high = adjust_price_by_fraction(latest_high_of_day)
        entry_price_str = f"{adjusted_entry_low} - {adjusted_entry_high}"
        
        stop_loss_calculation_base = float(adjusted_entry_low)
        
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

        tp1_val_adj, tp2_val_adj, tp3_val_adj = None, None, None
        tp_levels_raw = potential_tp_levels_from_history
        current_search_start_index = 0

        base_for_next_tp_min_target = adjusted_entry_high

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

        rr_tp1_str = "N/A"
        
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