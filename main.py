import os
from dotenv import load_dotenv
import requests
from datetime import datetime
from tkinter import Tk, Label, Frame

# Load environment variables
load_dotenv()

# --- Constants for Configuration ---
API_KEY = os.getenv("API_KEY")
BUS_STOP_CODE_A = os.getenv("BUS_STOP_CODE_A")
BUS_STOP_CODE_B = os.getenv("BUS_STOP_CODE_B")
WINDOW_TITLE = "Bus Arrival Times"
WINDOW_SIZE = "800x480"

# Color settings
BG_COLOR_MAIN = "#333333"
BG_COLOR_HEADER = "#444444"
BG_COLOR_CELL = "#f0f0f0"
BG_COLOR_CRITICAL = "#FF4C4C"
BG_COLOR_WARNING = "#FFA500"
BG_COLOR_NORMAL = "#f0f0f0"

# Font settings
FONT_HEADER = ("Arial", 35, "bold")
FONT_SECTION = ("Arial", 26, "bold")
FONT_SERVICE = ("Arial", 24)
FONT_TIME = ("Arial", 26, "bold")

# Foreground colors for text
FG_COLOR_HEADER = "white"
FG_COLOR_SECTION = "#ffcc00"
FG_COLOR_TIME_SD = "#0000ff"
FG_COLOR_TIME_DD = "#008000"
FG_COLOR_TIME_DEFAULT = "#000000"

# Other settings
UPDATE_INTERVAL_MS = 30000  # Update interval for bus info (milliseconds)
LABEL_PADDING = {"padx": 10, "pady": 5}
TIME_CELL_WIDTH = 5         # Width for the bus arrival time labels
SECTION_NAMES = [("Downstairs", BUS_STOP_CODE_A), ("Opposite", BUS_STOP_CODE_B)]

# --- Function to Fetch Bus Arrival Times ---
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

            # Loop through next three bus timings
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

# --- Function to Update Bus Timing Display ---
def update_display():
    # Clear previous bus info in each section frame
    for section_frame in section_frames:
        for widget in section_frame.winfo_children():
            widget.destroy()

    def create_row(frame, row, service_no, arrival_times, types):
        # Label for service number
        Label(
            frame,
            text=service_no,
            font=FONT_SERVICE,
            width=10,  # Fixed width for consistency
            anchor="center",
            bg=BG_COLOR_CELL,
        ).grid(row=row, column=0, **LABEL_PADDING, sticky="nsew")

        # Container for bus arrival times
        time_frame = Frame(frame, bg=BG_COLOR_CELL)
        time_frame.grid(row=row, column=1, **LABEL_PADDING, sticky="nsew")

        # Ensure proper column weight for consistent layout
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=3)

        # Populate arrival times with formatting based on bus type and timing
        for i, (time, bus_type) in enumerate(zip(arrival_times, types)):
            fg_color = (
                FG_COLOR_TIME_SD if bus_type == "SD" else
                FG_COLOR_TIME_DD if bus_type == "DD" else
                FG_COLOR_TIME_DEFAULT
            )

            if time <= 2:
                bg_color = BG_COLOR_CRITICAL
                fg_color = "white"  # For readability on a red background
            elif time <= 4:
                bg_color = BG_COLOR_WARNING
                fg_color = "black"
            else:
                bg_color = BG_COLOR_NORMAL

            bus_type_label = " (DD)" if bus_type == "DD" else ""

            # Combined label for time and bus type
            Label(
                time_frame,
                text=f"{time}m{bus_type_label}",
                font=FONT_TIME,
                width=TIME_CELL_WIDTH + 4,  # Adjust width for combined text
                anchor="center",
                bg=bg_color,
                fg=fg_color,
            ).grid(row=0, column=i, sticky="nsew")

    # Update each bus stop section with current bus info
    for section_idx, (section_name, bus_stop_code) in enumerate(SECTION_NAMES):
        bus_info = get_bus_arrival(API_KEY, bus_stop_code)
        for row, (service_no, arrival_times, types) in enumerate(bus_info):
            create_row(section_frames[section_idx], row, service_no, arrival_times, types)

    # Schedule next update for bus timings
    root.after(UPDATE_INTERVAL_MS, update_display)

# --- Function to Update the Time Every Second ---
def update_time():
    current_time = datetime.now().strftime("%I:%M:%S %p")
    time_label.config(text=current_time)
    root.after(1000, update_time)

# --- Initialize the Tkinter Window ---
root = Tk()
root.title(WINDOW_TITLE)
root.geometry(WINDOW_SIZE)
root.configure(bg=BG_COLOR_MAIN)

# Create a header frame to hold both the title and the live clock
header_frame = Frame(root, bg=BG_COLOR_HEADER)
header_frame.pack(fill="x")

# Title label for bus arrival display (aligned to left)
title_label = Label(
    header_frame,
    text="Bus Arrival Times",
    font=FONT_HEADER,
    bg=BG_COLOR_HEADER,
    fg=FG_COLOR_HEADER,
    pady=10
)
title_label.pack(side="left", padx=(10, 0))

# Time label to display current time with seconds (aligned to right)
time_label = Label(
    header_frame,
    font=FONT_SECTION,
    bg=BG_COLOR_HEADER,
    fg=FG_COLOR_HEADER,
    pady=10
)
time_label.pack(side="right", padx=(0, 10))

# Main container frame for bus info sections
main_frame = Frame(root, bg=BG_COLOR_MAIN)
main_frame.pack(expand=True, fill="both", padx=10, pady=10)
main_frame.grid_columnconfigure(0, weight=1)

# Create sections for each bus stop
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
    # Positioning: each section label and its corresponding frame are stacked vertically
    section_label.grid(row=row_idx * 2, column=0, **LABEL_PADDING, sticky="n")
    section_labels.append(section_label)

    section_frame = Frame(main_frame, bg=BG_COLOR_MAIN)
    section_frame.grid(row=row_idx * 2 + 1, column=0, **LABEL_PADDING, sticky="nsew")
    section_frames.append(section_frame)

# --- Start the Update Loops ---
update_display()  # Begin updating bus arrival info
update_time()     # Begin updating the live clock

# Run the Tkinter main loop
root.mainloop()