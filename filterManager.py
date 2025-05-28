import ttkbootstrap as ttk
from ttkbootstrap.constants import *

class FilterManager:
    def __init__(self, parent_frame, advanced_mode_variable):
        self.parent_frame = parent_frame
        self.advanced_mode_var = advanced_mode_variable
        self.break_high_vars = {}
        self.technical_vars = {}
        self.technical_frames = []
        self.trend_line_confirmation_var = ttk.BooleanVar(value=False)
        self.setup_filters()

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
            tech_options.update({
                "use_custom_ema_1": "Use Custom EMA 1 (Short Period)",
                "use_custom_ema_2": "Use Custom EMA 2 (Long Period)",
            })
        else:
            tech_options.update({
                "ema_20": "Price Above EMA 20",
                "ema_60": "Price Above EMA 60",
            })
        
        # Common technical indicators
        tech_options.update({
            "macd": "MACD Bullish (GC)",
            "stochastic": "Stochastic Bullish (GC)",
            "volume": "Volume Above 5 and/or 20 Days High"
        })

        for key, text in tech_options.items():
            var = ttk.BooleanVar(value=False)
            self.technical_vars[key] = var
            chk = ttk.Checkbutton(self.tech_indicators_frame, text=text, variable=var, state=DISABLED)
            chk.pack(anchor=W, pady=2)
            self.technical_frames.append(chk)

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
        
        for frame in self.technical_frames:
            frame.configure(state=new_state)

    def get_selected_filters(self):
        """Returns a dictionary of all selected filters"""
        filters = {
            "break_high": {k: v.get() for k, v in self.break_high_vars.items()},
            "technical": {k: v.get() for k, v in self.technical_vars.items()},
            "trend_line_confirmation": self.trend_line_confirmation_var.get()
        }
        return filters

    def is_valid_selection(self):
        """Check if at least one Break High Price filter is selected"""
        return any(var.get() for var in self.break_high_vars.values()) 