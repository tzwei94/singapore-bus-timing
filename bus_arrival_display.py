import os
import time
from dotenv import load_dotenv
import requests
from datetime import datetime
from tkinter import Tk, Label, StringVar, Frame

# Load environment variables
load_dotenv()

def get_bus_arrival(api_key, bus_stop_code):
    url = "https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival?BusStopCode=" + bus_stop_code
    headers = {
        'AccountKey': api_key,
        'accept': 'application/json'
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        services = data.get("Services", [])
        bus_info = []
        
        for service in services:
            service_no = service["ServiceNo"]
            arrival_times = []
            for bus in ["NextBus", "NextBus2", "NextBus3"]:
                if service.get(bus):
                    eta = service[bus]["EstimatedArrival"]
                    if eta:
                        eta_time = datetime.strptime(eta, "%Y-%m-%dT%H:%M:%S%z")
                        time_diff = (eta_time - datetime.now(eta_time.tzinfo)).total_seconds() / 60
                        arrival_times.append(round(time_diff))
            if arrival_times:
                bus_info.append((service_no, arrival_times))
        return bus_info
    else:
        return []

def update_display():
    # Fetch bus information
    bus_info_A = get_bus_arrival(api_key, bus_stop_code_A)
    bus_info_B = get_bus_arrival(api_key, bus_stop_code_B)

    # Clear old data
    for widget in downstairs_frame.winfo_children():
        widget.destroy()
    for widget in opposite_frame.winfo_children():
        widget.destroy()

    # Update "Downstairs" section
    for row, (service_no, arrival_times) in enumerate(bus_info_A):
        Label(downstairs_frame, text=service_no, font=("Arial", 16), width=5, anchor="center").grid(row=row, column=0, padx=5, pady=2)
        Label(downstairs_frame, text=" | ".join(map(str, arrival_times)), font=("Arial", 16), anchor="w").grid(row=row, column=1, padx=5, pady=2)

    # Update "Opposite" section
    for row, (service_no, arrival_times) in enumerate(bus_info_B):
        Label(opposite_frame, text=service_no, font=("Arial", 16), width=5, anchor="center").grid(row=row, column=0, padx=5, pady=2)
        Label(opposite_frame, text=" | ".join(map(str, arrival_times)), font=("Arial", 16), anchor="w").grid(row=row, column=1, padx=5, pady=2)

    # Schedule next update
    root.after(30000, update_display)

# Initialize Raspberry Pi display
api_key = os.getenv('API_KEY')
bus_stop_code_A = os.getenv('BUS_STOP_CODE_A')
bus_stop_code_B = os.getenv('BUS_STOP_CODE_B')

# Create Tkinter root window
root = Tk()
root.title("Bus Arrival Times")
root.geometry("800x480")  # Adjust to your Raspberry Pi screen resolution

# Create main frames
main_frame = Frame(root)
main_frame.pack(expand=True, fill="both")

# Create "Downstairs" section
downstairs_label = Label(main_frame, text="Downstairs", font=("Arial", 20, "bold"))
downstairs_label.grid(row=0, column=0, padx=10, pady=10)

downstairs_frame = Frame(main_frame)
downstairs_frame.grid(row=1, column=0, padx=10, pady=10)

# Create "Opposite" section
opposite_label = Label(main_frame, text="Opposite", font=("Arial", 20, "bold"))
opposite_label.grid(row=0, column=1, padx=10, pady=10)

opposite_frame = Frame(main_frame)
opposite_frame.grid(row=1, column=1, padx=10, pady=10)

# Start updating the display
update_display()

# Run the Tkinter main loop
root.mainloop()
