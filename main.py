import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import requests

root = ttk.Window(themename="darkly")
root.title("Trading Plan Generator")
root.geometry("800x600")
root.resizable(False, False)

center_frame = ttk.Frame(root)
center_frame.pack(expand=True, fill=BOTH)
center_frame.place(relx=0.5, rely=0.5, anchor=CENTER)

# --- API check ---
api_status_label = ttk.Label(center_frame, text="Checking API availability...")
api_status_label.grid(column=0, row=1, padx=10, pady=10)
spinner = ttk.Progressbar(center_frame, orient=HORIZONTAL, length=300)
spinner.grid(column=0, row=0, padx=10, pady=10)
spinner.start()

# --- Main app UI (hidden until API is available) ---
def show_main_app():
    api_status_label.grid_remove()
    spinner.grid_remove()
    
    trading_plan_frame = ttk.Frame(root, padding=10, borderwidth=1, relief="groove")
    trading_plan_frame.pack(fill=X, padx=10, pady=20)

    header_frame = ttk.Frame(trading_plan_frame)
    header_frame.pack(fill=X)

    header_label = ttk.Label(header_frame, text="Generated Trading Plans", font=("Helvetica", 12, "bold"))
    header_label.pack(side=LEFT)

    create_button = ttk.Button(header_frame, text="Create", command=create_trading_plan, bootstyle="warning")
    create_button.pack(side=RIGHT)

    content_frame = ttk.Frame(trading_plan_frame)
    content_frame.pack(fill=BOTH, expand=True, pady=10)

    placeholder_label = ttk.Label(content_frame, text="List of your generated trading plans", anchor=CENTER)
    placeholder_label.pack()

def create_trading_plan():
    from tkinter import messagebox

    messagebox.showinfo("Create Trading Plan", "This feature is not yet implemented.")

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
                    root.after(500, show_main_app)
                    spinner.stop()
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

def on_close():
    root.destroy()

root.mainloop()