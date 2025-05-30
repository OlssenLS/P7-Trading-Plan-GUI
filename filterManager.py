import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import simpledialog # Added for the modal

class FilterManager:
    def __init__(self, parent_frame, advanced_mode_variable):
        self.parent_frame = parent_frame
        self.advanced_mode_var = advanced_mode_variable
        self.break_high_vars = {}
        self.technical_vars = {}
        self.technical_frames = []
        self.trend_line_confirmation_var = ttk.BooleanVar(value=False)
        # New variables for custom EMA
        self.use_custom_ema_var = ttk.BooleanVar(value=False)
        self.custom_ema_short_period = ttk.StringVar(value="9") # Default
        self.custom_ema_long_period = ttk.StringVar(value="21") # Default
        self.setup_filters()

    def open_ema_settings_modal(self):
        modal = ttk.Toplevel(self.parent_frame)
        modal.title("Set Custom EMA Periods")
        modal.transient(self.parent_frame) # Make modal appear on top of parent
        modal.grab_set() # Disable interaction with parent window

        # Center the modal (basic centering)
        modal.update_idletasks()
        parent_x = self.parent_frame.winfo_rootx()
        parent_y = self.parent_frame.winfo_rooty()
        parent_width = self.parent_frame.winfo_width()
        parent_height = self.parent_frame.winfo_height()
        modal_width = modal.winfo_width()
        modal_height = modal.winfo_height()
        x = parent_x + (parent_width // 2) - (modal_width // 2)
        y = parent_y + (parent_height // 2) - (modal_height // 2)
        # A more robust centering might be needed, for now, simple geometry
        modal.geometry(f"300x150+{x}+{y}") # Adjusted size for content

        frame = ttk.Frame(modal, padding=20)
        frame.pack(expand=True, fill=BOTH)

        ttk.Label(frame, text="Short EMA Period:").grid(row=0, column=0, padx=5, pady=5, sticky=W)
        short_ema_entry = ttk.Entry(frame, textvariable=self.custom_ema_short_period, width=5)
        short_ema_entry.grid(row=0, column=1, padx=5, pady=5, sticky=W)

        ttk.Label(frame, text="Long EMA Period:").grid(row=1, column=0, padx=5, pady=5, sticky=W)
        long_ema_entry = ttk.Entry(frame, textvariable=self.custom_ema_long_period, width=5)
        long_ema_entry.grid(row=1, column=1, padx=5, pady=5, sticky=W)

        def save_settings():
            try:
                short = int(self.custom_ema_short_period.get())
                long = int(self.custom_ema_long_period.get())
                if short <= 0 or long <= 0:
                    simpledialog.messagebox.showerror("Invalid Input", "EMA periods must be positive integers.", parent=modal)
                    return
                if short == long:
                    simpledialog.messagebox.showwarning("Input Info", "Short and Long EMA periods are the same.", parent=modal)
                # Values are already bound to the StringVars, so they are saved
                modal.destroy()
            except ValueError:
                simpledialog.messagebox.showerror("Invalid Input", "EMA periods must be valid integers.", parent=modal)

        def cancel_settings():
            # Optionally, revert to previous values if needed, or just close
            modal.destroy()

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        save_button = ttk.Button(button_frame, text="Save", command=save_settings, bootstyle="success")
        save_button.pack(side=LEFT, padx=5)
        
        cancel_button = ttk.Button(button_frame, text="Cancel", command=cancel_settings, bootstyle="secondary")
        cancel_button.pack(side=LEFT, padx=5)
        
        # Ensure entries are focused for user convenience
        short_ema_entry.focus_set()

    def setup_filters(self):
        # Break High Price Filters Section
        break_high_frame = ttk.LabelFrame(self.parent_frame, text="Break High Price Filters (Select at least one)", padding=10)
        break_high_frame.pack(fill=X, padx=10, pady=5)

        # Break High Price options
        break_high_options = {
            "1_day": "1 Day High Price",
            "5_days": "5 Days High Price",
            "1_month": "1 Month High Price",
            "2_months": "2 Months High Price",
            "3_months": "3 Months High Price"
        }

        for key, text in break_high_options.items():
            var = ttk.BooleanVar(value=False)
            self.break_high_vars[key] = var
            chk = ttk.Checkbutton(break_high_frame, text=text, variable=var, command=self.on_break_high_change)
            chk.pack(anchor=W, pady=2)

        # Technical Indicators Section
        self.tech_indicators_frame = ttk.LabelFrame(self.parent_frame, text="Technical Indicators (Optional)", padding=10)
        self.tech_indicators_frame.pack(fill=X, padx=10, pady=5)

        # Technical indicator options
        tech_options = {}
        if self.advanced_mode_var.get():
            # Frame for custom EMA checkbox and button
            custom_ema_frame = ttk.Frame(self.tech_indicators_frame)
            custom_ema_frame.pack(anchor=W, fill=X)

            self.technical_vars["use_custom_ema"] = self.use_custom_ema_var # Store the var
            chk_custom_ema = ttk.Checkbutton(custom_ema_frame, text="Use Custom EMA Values", variable=self.use_custom_ema_var, state=DISABLED)
            chk_custom_ema.pack(side=LEFT, pady=2)
            self.technical_frames.append(chk_custom_ema) # Add to list for enable/disable

            ema_settings_button = ttk.Button(custom_ema_frame, text="(Set EMA)", command=self.open_ema_settings_modal, bootstyle="link")
            ema_settings_button.pack(side=LEFT, padx=5, pady=2)
            # Initially disable button if checkbox is not checked (or enable if var is True)
            ema_settings_button.config(state=NORMAL if self.use_custom_ema_var.get() else DISABLED)

            def toggle_ema_button_state(*args):
                ema_settings_button.config(state=NORMAL if self.use_custom_ema_var.get() else DISABLED)
            
            self.use_custom_ema_var.trace_add("write", toggle_ema_button_state)

        else: # Non-advanced mode EMA options
            tech_options.update({
                "ema_20": "Price Above EMA 20",
                "ema_60": "Price Above EMA 60",
            })
        
        # Common technical indicators (added after potential advanced EMA setup)
        common_tech_options = {
            "macd": "MACD Bullish (GC)",
            "stochastic": "Stochastic Bullish (GC)",
            "volume": "Volume Above 5 and/or 20 Days High"
        }
        tech_options.update(common_tech_options) # Add these to the dict

        # Create checkboxes for non-advanced EMA and common indicators
        for key, text in tech_options.items():
            if key in ["ema_20", "ema_60"] and self.advanced_mode_var.get(): # Skip if advanced mode already handled custom EMA
                continue
            
            var = ttk.BooleanVar(value=False)
            self.technical_vars[key] = var # Store var
            chk = ttk.Checkbutton(self.tech_indicators_frame, text=text, variable=var, state=DISABLED)
            chk.pack(anchor=W, pady=2)
            self.technical_frames.append(chk) # Add to list for enable/disable

        # Trend Line Confirmation Section
        trend_line_frame = ttk.LabelFrame(self.parent_frame, text="Manual Confirmation", padding=10)
        trend_line_frame.pack(fill=X, padx=10, pady=5)

        self.trend_line_chk = ttk.Checkbutton(
            trend_line_frame,
            text="Include Trend Line Confirmation",
            variable=self.trend_line_confirmation_var,
        )
        self.trend_line_chk.pack(anchor=W, pady=2)

    def on_break_high_change(self):
        """Enable/disable technical indicators based on Break High Price selection"""
        any_break_high_selected = any(var.get() for var in self.break_high_vars.values())
        new_state = NORMAL if any_break_high_selected else DISABLED
        
        for frame_widget in self.technical_frames: # Changed from self.technical_frames to frame_widget
            frame_widget.configure(state=new_state)
        
        # Also handle the EMA settings button state
        if self.advanced_mode_var.get():
            # Find the 'Set EMA' button. This is a bit fragile; a direct reference would be better.
            # Assuming it's the only button directly parented by custom_ema_frame
            # Or, we could store a reference to it. For now, let's assume this structure.
            # We need to find the custom_ema_frame first.
            # The button state is also managed by use_custom_ema_var trace.
            # This on_break_high_change should only enable/disable the checkbox.
            # The trace will handle the button based on the checkbox.
            
            # Re-evaluate button state based on checkbox state if tech indicators are enabled/disabled overall
            if "use_custom_ema" in self.technical_vars: # Check if the var/widget was created
                use_custom_ema_checkbox = None
                for widget in self.tech_indicators_frame.winfo_children():
                    if isinstance(widget, ttk.Frame): # The custom_ema_frame
                        for chk_btn_widget in widget.winfo_children():
                            if isinstance(chk_btn_widget, ttk.Checkbutton) and chk_btn_widget.cget("text") == "Use Custom EMA Values":
                                use_custom_ema_checkbox = chk_btn_widget
                            if isinstance(chk_btn_widget, ttk.Button) and chk_btn_widget.cget("text") == "Set EMA":
                                if new_state == NORMAL and self.use_custom_ema_var.get():
                                    chk_btn_widget.config(state=NORMAL)
                                else:
                                    chk_btn_widget.config(state=DISABLED)
                if use_custom_ema_checkbox:
                     use_custom_ema_checkbox.config(state=new_state)

    def get_selected_filters(self):
        """Returns a dictionary of all selected filters"""
        filters = {
            "break_high": {k: v.get() for k, v in self.break_high_vars.items()},
            "technical": {k: v.get() for k, v in self.technical_vars.items() if k not in ["use_custom_ema"]}, # Exclude the control var
            "trend_line_confirmation": self.trend_line_confirmation_var.get()
        }
        if self.advanced_mode_var.get() and self.use_custom_ema_var.get():
            filters["technical"]["use_custom_ema"] = True # Signal that custom EMAs are active
            filters["technical"]["ema1_period"] = self.custom_ema_short_period.get()
            filters["technical"]["ema2_period"] = self.custom_ema_long_period.get()
        elif self.advanced_mode_var.get(): # Advanced mode but custom EMA not checked
             filters["technical"]["use_custom_ema"] = False
        return filters

    def is_valid_selection(self):
        """Check if at least one Break High Price filter is selected"""
        return any(var.get() for var in self.break_high_vars.values()) 