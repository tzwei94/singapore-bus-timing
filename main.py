import os
import time
from dotenv import load_dotenv
import requests
from datetime import datetime
from tkinter import Tk, Label, Frame

# Load environment variables
load_dotenv()

def get_bus_arrival(api_key, bus_stop_code):
    url = f"https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival?BusStopCode={bus_stop_code}"
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

    # Function to create a row with dynamic styling
    def create_row(frame, row, service_no, arrival_times):
        bg_color = "#f0f0f0" if row % 2 == 0 else "#ffffff"

        # Service number
        Label(
            frame,
            text=service_no,
            font=("Arial", 20),  # Larger font size for service number
            width=10,
            anchor="center",
            bg=bg_color,
        ).grid(row=row, column=0, padx=5, pady=2)

        # Create a frame to hold individual arrival times
        time_frame = Frame(frame, bg=bg_color)
        time_frame.grid(row=row, column=1, padx=5, pady=2, sticky="w")

        # Display each arrival time as an individual label with highlighting
        for i, time in enumerate(arrival_times):
            fg_color = "#ff0000" if time < 3 else "#000000"  # Red for urgent times
            Label(
                time_frame,
                text=f"{time}",  # Display only the time
                font=("Arial", 24, "bold"),  # Larger font for times
                width=5,  # Consistent width for alignment
                anchor="center",
                bg=bg_color,
                fg=fg_color,
            ).grid(row=0, column=i, padx=10)  # Added padding for better spacing

    # Update "Downstairs" section
    for row, (service_no, arrival_times) in enumerate(bus_info_A):
        create_row(downstairs_frame, row, service_no, arrival_times)

    # Update "Opposite" section
    for row, (service_no, arrival_times) in enumerate(bus_info_B):
        create_row(opposite_frame, row, service_no, arrival_times)

    # Schedule next update
    root.after(5000, update_display)


# Initialize Raspberry Pi display
api_key = os.getenv('API_KEY')
bus_stop_code_A = os.getenv('BUS_STOP_CODE_A')
bus_stop_code_B = os.getenv('BUS_STOP_CODE_B')

# Create Tkinter root window
root = Tk()
root.title("Bus Arrival Times")
root.geometry("800x480")  # Adjust to your Raspberry Pi screen resolution
root.configure(bg="#333333")  # Dark background for better contrast

# Header
header = Label(root, text="Bus Arrival Times", font=("Arial", 30, "bold"), bg="#444444", fg="white", pady=10)
header.pack(fill="x")

# Create main frames
main_frame = Frame(root, bg="#333333")
main_frame.pack(expand=True, fill="both", padx=10, pady=10)

# Create "Downstairs" section
downstairs_label = Label(main_frame, text="Downstairs", font=("Arial", 24, "bold"), bg="#333333", fg="#ffcc00")
downstairs_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

downstairs_frame = Frame(main_frame, bg="#333333")
downstairs_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

# Create "Opposite" section
opposite_label = Label(main_frame, text="Opposite", font=("Arial", 24, "bold"), bg="#333333", fg="#ffcc00")
opposite_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

opposite_frame = Frame(main_frame, bg="#333333")
opposite_frame.grid(row=3, column=0, padx=10, pady=10, sticky="w")

# Start updating the display
update_display()

# Run the Tkinter main loop
root.mainloop()