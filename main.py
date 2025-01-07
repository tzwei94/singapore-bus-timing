import os
from dotenv import load_dotenv
import requests
from datetime import datetime
from tkinter import Tk, Label, Frame

# Load environment variables
load_dotenv()

# Constants for configuration
API_KEY = os.getenv("API_KEY")
BUS_STOP_CODE_A = os.getenv("BUS_STOP_CODE_A")
BUS_STOP_CODE_B = os.getenv("BUS_STOP_CODE_B")
WINDOW_TITLE = "Bus Arrival Times"
WINDOW_SIZE = "800x480"
BG_COLOR_MAIN = "#333333"
BG_COLOR_HEADER = "#444444"
BG_COLOR_CELL = "#f0f0f0"
BG_COLOR_URGENT = "#ffcc00"
FONT_HEADER = ("Arial", 35, "bold")
FONT_SECTION = ("Arial", 26, "bold")
FONT_SERVICE = ("Arial", 24)
FONT_TIME = ("Arial", 26, "bold")
FG_COLOR_HEADER = "white"
FG_COLOR_SECTION = "#ffcc00"
FG_COLOR_TIME_SD = "#0000ff"
FG_COLOR_TIME_DD = "#008000"
FG_COLOR_TIME_DEFAULT = "#000000"
UPDATE_INTERVAL_MS = 30000  # Update interval in milliseconds
LABEL_PADDING = {"padx": 10, "pady": 5}
TIME_CELL_WIDTH = 5  # Width of time labels
SECTION_NAMES = [("Downstairs", BUS_STOP_CODE_A), ("Opposite", BUS_STOP_CODE_B)]

# Fetch bus arrival times from the API
def get_bus_arrival(api_key, bus_stop_code):
    url = f"https://datamall2.mytransport.sg/ltaodataservice/v3/BusArrival?BusStopCode={bus_stop_code}"
    headers = {"AccountKey": api_key, "accept": "application/json"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        services = data.get("Services", [])
        bus_info = []

        for service in services:
            service_no = service["ServiceNo"]
            arrival_times = []
            types = []

            for bus in ["NextBus", "NextBus2", "NextBus3"]:
                if service.get(bus):
                    eta = service[bus]["EstimatedArrival"]
                    bus_type = service[bus].get("Type", "Other")
                    if eta:
                        eta_time = datetime.strptime(eta, "%Y-%m-%dT%H:%M:%S%z")
                        time_diff = (eta_time - datetime.now(eta_time.tzinfo)).total_seconds() / 60
                        arrival_times.append(round(time_diff))
                        types.append(bus_type)
            if arrival_times:
                bus_info.append((service_no, arrival_times, types))
        return bus_info
    else:
        return []

# Update the display with bus timings
def update_display():
    # Clear previous data
    for section_frame in section_frames:
        for widget in section_frame.winfo_children():
            widget.destroy()

    # Create a row in the grid
    def create_row(frame, row, service_no, arrival_times, types):
        # Service number
        Label(
            frame,
            text=service_no,
            font=FONT_SERVICE,
            width=10,  # Fixed width for uniformity
            anchor="center",
            bg=BG_COLOR_CELL,
        ).grid(row=row, column=0, **LABEL_PADDING, sticky="nsew")

        # Time cells container
        time_frame = Frame(frame, bg=BG_COLOR_CELL)
        time_frame.grid(row=row, column=1, **LABEL_PADDING, sticky="nsew")

        # Configure grid columns for consistent width
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=3)

        # Populate arrival times
        for i, (time, bus_type) in enumerate(zip(arrival_times, types)):
            fg_color = (
                FG_COLOR_TIME_SD if bus_type == "SD" else
                FG_COLOR_TIME_DD if bus_type == "DD" else
                FG_COLOR_TIME_DEFAULT
            )
            bg_color = BG_COLOR_URGENT if time < 3 else BG_COLOR_CELL

            Label(
                time_frame,
                text=f"{time}",
                font=FONT_TIME,
                width=TIME_CELL_WIDTH,
                anchor="center",
                bg=bg_color,
                fg=fg_color,
            ).grid(row=0, column=i, sticky="nsew")

    # Populate each section
    for section_idx, (section_name, bus_stop_code) in enumerate(SECTION_NAMES):
        bus_info = get_bus_arrival(API_KEY, bus_stop_code)
        for row, (service_no, arrival_times, types) in enumerate(bus_info):
            create_row(section_frames[section_idx], row, service_no, arrival_times, types)

    # Schedule the next update
    root.after(UPDATE_INTERVAL_MS, update_display)

# Initialize the Tkinter window
root = Tk()
root.title(WINDOW_TITLE)
root.geometry(WINDOW_SIZE)
root.configure(bg=BG_COLOR_MAIN)

# Header
header = Label(
    root, 
    text="Bus Arrival Times", 
    font=FONT_HEADER, 
    bg=BG_COLOR_HEADER, 
    fg=FG_COLOR_HEADER, 
    pady=10
)
header.pack(fill="x")

# Main container
main_frame = Frame(root, bg=BG_COLOR_MAIN)
main_frame.pack(expand=True, fill="both", padx=10, pady=10)

# Configure grid for main_frame to ensure proper centering
main_frame.grid_columnconfigure(0, weight=1)  # Center all contents horizontally

# Create sections dynamically
section_labels = []
section_frames = []

for row_idx, (section_name, _) in enumerate(SECTION_NAMES):
    section_label = Label(
        main_frame, 
        text=section_name, 
        font=FONT_SECTION, 
        bg=BG_COLOR_MAIN, 
        fg=FG_COLOR_SECTION
    )
    section_label.grid(row=row_idx * 2, column=0, **LABEL_PADDING, sticky="n")  # Align label to the middle
    section_labels.append(section_label)

    section_frame = Frame(main_frame, bg=BG_COLOR_MAIN)
    section_frame.grid(row=row_idx * 2 + 1, column=0, **LABEL_PADDING, sticky="nsew")  # Align frame to fill available space
    section_frames.append(section_frame)

# Start the update loop
update_display()

# Run the application
root.mainloop()
