import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import threading
import requests

root = ttk.Window(themename="darkly")
root.title("Trading Plan Generator")
root.geometry("800x600")
root.resizable(False, False)

# --- API check ---
api_status_label = ttk.Label(root, text="Checking API availability...")
api_status_label.grid(column=0, row=1, padx=10, pady=10)
spinner = ttk.Progressbar(root, orient=HORIZONTAL, length=300, mode='indeterminate')
spinner.grid(column=0, row=0, padx=10, pady=10)
spinner.start()

# --- Main app UI (hidden until API is available) ---
def show_main_app():
    api_status_label.grid_remove()
    spinner.grid_remove()
    ttk.Label(root, text="Main App Loaded!").grid(column=0, row=0, padx=10, pady=10)

def check_api_availability(max_retries=10):
    base_url = "https://yfinance-web-indonesia-data.vercel.app"
    endpoint_url = f"{base_url}/api/stocks?start_date=2023-01-01"
    for attempt in range(max_retries):
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                root.after(0, lambda: api_status_label.config(text="API is available!"))
                root.after(500, show_main_app)
                break
            else:
                raise Exception("API not available")
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            else:
                root.after(0, lambda: api_status_label.config(text="API is not available!"))
        
    spinner.stop()

def start_api_check():
    threading.Thread(target=check_api_availability, daemon=True).start()

root.after(100, start_api_check)

def on_close():
    if ttk.messagebox.askokcancel("Quit", "Do you want to quit?"):
        root.destroy()

root.mainloop()