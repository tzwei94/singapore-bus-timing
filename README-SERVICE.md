# Singapore Bus Timing Service Setup

Follow these steps to create and enable your systemd service for the Singapore Bus Timing Script.

---

## Step 1: Open the Service File with Vi

Open the file for editing using **vi**:

```bash
sudo vi /etc/systemd/system/singapore-bus-timing.service
```

---

## Step 2: Paste the Service File Content

In **vi**, press `i` to enter insert mode and paste the following content:

```ini
[Unit]
Description=Singapore Bus Timing Script Service
After=network.target

[Service]
# User and working directory
User=tzwei
WorkingDirectory=/home/tzwei/singapore-bus-timing

# Set the DISPLAY environment variable for the physical screen
Environment=DISPLAY=:0

# Command to run the script
ExecStart=/home/tzwei/singapore-bus-timing/.venv/bin/python /home/tzwei/singapore-bus-timing/main.py

# Restart policy
Restart=always

[Install]
WantedBy=multi-user.target
```

When finished, press `Esc` and type `:wq` to save and exit **vi**.

---

## Step 3: Reload the Systemd Daemon

Apply the new service configuration:

```bash
sudo systemctl daemon-reload
```

---

## Step 4: Enable the Service at Boot

Enable the service so that it starts automatically at system boot:

```bash
sudo systemctl enable singapore-bus-timing.service
```

---

## Step 5: Start the Service

Start your service immediately:

```bash
sudo systemctl start singapore-bus-timing.service
```

---

## Step 6: Check the Service Status

Verify that the service is running correctly:

```bash
sudo systemctl status singapore-bus-timing.service
```
