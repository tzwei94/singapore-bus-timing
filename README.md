# Singapore Bus Timing

Native Tkinter display for two Singapore bus stops, sized for an 800×480 screen.

## Setup

Raspberry Pi OS Lite (32-bit) needs Python's Tkinter package and a running X11 session. A full desktop is optional. For a minimal X11 setup:

```bash
sudo apt update
sudo apt install python3-venv python3-tk xserver-xorg xinit openbox
```

From the Pi's local console, start a minimal session with `startx /usr/bin/openbox-session -- :0`. Arrange for that session to start at boot if using the systemd service; setting `DISPLAY=:0` alone does not start X11. See [service setup](README-SERVICE.md).

In the project directory, create and activate a virtual environment, then install the packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your LTA DataMall API key and the two bus stop codes. Keep the key private; do not commit `.env`.

```dotenv
# Get the API key from LTA DataMall.
API_KEY=your_lta_api_key
BUS_STOP_CODE_A=your_first_bus_stop_code
BUS_STOP_CODE_B=your_second_bus_stop_code
```

## Usage

Run in a working graphical session:

```bash
source .venv/bin/activate
python main.py
```

The app polls both stops on one background worker, leaving the clock and interface responsive during HTTP requests. It refreshes every 30 seconds and retries after errors. Each request has a 3.05-second connect timeout and a 10-second read timeout; these are not a total end-to-end deadline.

A failed stop retains its last successful arrivals with a visible retrying/stale status, while the other stop can still update. Countdowns are recalculated every second from arrival timestamps, and expired arrivals disappear even when offline. A successful response with no services shows an explicit empty state. Errors are logged to stderr, or the journal when run as a service.

Malformed arrival slots retain the previous estimate and mark the stop stale until a valid response arrives. Legitimately empty slots show `--`.

## Arrival icons

Each populated arrival has a source icon: a clock for operator-schedule times (`Monitored=0`), a location pin for location-based predictions (`Monitored=1`), or `?` when the source is unknown. A two-level bus silhouette replaces `(DD)` for double-deckers. A compact legend appears below the board.

Red and orange backgrounds retain their arrival-urgency meaning. Source icons describe how the estimate was obtained; the separate stale/retrying status describes freshness. Empty or expired slots show no icons. The icons use native Canvas shapes, so no emoji font or new package is required.

## Tests

The data and refresh tests use Python's standard-library test runner:

```bash
python -m unittest discover -s tests -v
```
