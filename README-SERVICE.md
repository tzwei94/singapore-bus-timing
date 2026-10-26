# Singapore Bus Timing Service Setup

Complete the [application setup](README.md) first and verify `python main.py` works in an X11 session. Raspberry Pi OS Lite needs `python3-tk` and a minimal X11 session; a full desktop is optional.

The service below runs the application on an existing X11 display. **`DISPLAY=:0` does not start X11.** Configure your Pi's local graphical session to start at boot as the same user, or start it manually from the local console before starting the service. If the display or X11 authorization file differs, adjust the example accordingly.

## Install the service

Create `/etc/systemd/system/singapore-bus-timing.service`:

```bash
sudo vi /etc/systemd/system/singapore-bus-timing.service
```

Replace `tzwei` and `/home/tzwei/singapore-bus-timing` with your username and checkout path. `XAUTHORITY` must point to the authorization file used by that user's X11 session.

```ini
[Unit]
Description=Singapore Bus Timing Display
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=tzwei
WorkingDirectory=/home/tzwei/singapore-bus-timing
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/tzwei/.Xauthority
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/tzwei/singapore-bus-timing/.venv/bin/python /home/tzwei/singapore-bus-timing/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

The app reads `.env` from its project directory. Keep that file readable by the configured service user. `network-online.target` provides startup ordering; it does not guarantee DataMall is reachable. The app retries failed refreshes automatically.

Reload systemd, enable startup, and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now singapore-bus-timing.service
```

After updating application code or `.env`, restart it:

```bash
sudo systemctl restart singapore-bus-timing.service
```

Run `daemon-reload` again before restarting if you changed the service file.

## Check startup and refresh failures

```bash
sudo systemctl status singapore-bus-timing.service --no-pager
sudo journalctl -u singapore-bus-timing.service -b -n 100 --no-pager
sudo journalctl -u singapore-bus-timing.service -f
```

- A Tkinter `no display` or `couldn't connect to display` error means X11 is unavailable, the display number is wrong, or the service user lacks the session's authorization. Verify the local X11 session and its `DISPLAY`/`XAUTHORITY` values.
- HTTP, timeout, and response errors appear in the journal. Verify the key and stop codes in `.env`, network access, and the Pi's date/time. Logs do not need the API key itself.
- A ticking clock confirms the UI loop is alive. Check each stop's retrying/stale status to tell whether arrivals are refreshing. During a failure, old arrivals continue counting down and disappear when expired.

`Restart=always` restarts an exited process. It cannot detect a still-running process whose refresh has frozen. Recovery from ordinary HTTP and response failures happens inside the application; a manual service restart is a diagnostic step if it remains stuck.
