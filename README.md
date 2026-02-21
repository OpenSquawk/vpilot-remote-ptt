# Remote VATSIM

Control VATSIM radio transmissions from anywhere — phone, tablet, or another PC.

---

## The Problem

You want to transmit on VATSIM, but you are not sitting at the PC running vPilot.

Maybe you are a pilot mentor helping a student through their first flight — the student has vPilot running on their PC, but you are across the room, in another building, or in another country. Maybe you are an ATC controller who stepped away but can still be reached by phone. Maybe you just want to transmit from your couch while your PC is at your desk.

The issue is that vPilot only accepts microphone input from a local audio device and PTT key presses from the local keyboard. There is no built-in remote control. If you are not physically at the machine, you cannot transmit.

## The Solution

Remote VATSIM bridges the gap with two components:

1. **Audio routing** — VB-Audio Virtual Cable takes your VoIP audio (Discord, Zoom, a phone call, any voice app) and pipes it into vPilot as if it were a local microphone.
2. **PTT control** — A Python server exposes a Push-to-Talk button in any web browser via WebSocket. Press and hold the button on your phone, and the server simulates the PTT key press on the PC.

Together, your voice reaches vPilot through the virtual cable, and your PTT command reaches vPilot through a simulated key press. From vPilot's perspective, it looks like someone is sitting at the PC talking into a mic and pressing a key.

### Architecture

```
Phone/Browser ──WebSocket──> Python Server ──> PTT Key Press ──> vPilot
                                                                   ^
VoIP App ──Audio Output──> VB-Cable ──Virtual Mic─────────────────-┘
```

## Features

- **Browser-based PTT button** — works on any device with a web browser
- **Desktop GUI** — local control panel for monitoring and configuration
- **Touch-friendly mobile interface** — large PTT button designed for phone use
- **Auto-reconnecting WebSocket** — connection drops are handled automatically
- **Configurable PTT key** — choose whichever key vPilot expects (Caps Lock, Scroll Lock, etc.)
- **Interactive setup wizard** — guided first-time configuration
- **Zero audio latency** — VB-Cable operates at the driver level, not through software mixing

## Prerequisites

- **Windows PC** running vPilot (or any VATSIM client that accepts a PTT key)
- **Python 3.8+**
- **VB-Audio Virtual Cable** (free) — [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/)

## Quick Start

```bash
# 1. Run the guided setup
python setup.py

# 2. Start the server
python gui.py              # with desktop GUI
# or
python remote_vatsim.py    # headless (no GUI)

# 3. Open the URL shown in the console on your phone/tablet/browser and press PTT
```

That is it. The setup wizard walks you through everything the first time.

## Detailed Setup Guide

### Step 1: Install VB-Audio Virtual Cable

1. Download the installer from [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/).
2. Extract the zip and run the installer as administrator.
3. Reboot your PC if prompted.

After installation, you will have two new audio devices on your system:

- **CABLE Input (VB-Audio Virtual Cable)** — this is the virtual speaker (audio goes *in* here)
- **CABLE Output (VB-Audio Virtual Cable)** — this is the virtual microphone (audio comes *out* here)

### Step 2: Configure Audio Routing

The goal is to route your voice from a VoIP app into vPilot.

**In your VoIP app (Discord, Zoom, Teams, phone bridge, etc.):**

- Set the **Output Device** (speakers/headphones) to **CABLE Input (VB-Audio Virtual Cable)**
- This sends the remote person's voice into the virtual cable

**In vPilot:**

- Set the **Microphone** to **CABLE Output (VB-Audio Virtual Cable)**
- This makes vPilot receive audio from the virtual cable as if it were a real mic

Now when someone speaks on the VoIP call, their voice flows through the virtual cable and into vPilot.

### Step 3: Run the Setup Wizard

```bash
python setup.py
```

The wizard will ask you to configure:

- Which key to use for PTT (default: Caps Lock)
- Which ports to use for the web UI and WebSocket

It generates a `config.json` file with your settings.

### Step 4: Configure vPilot PTT

Open vPilot settings and set the PTT key to match whatever you chose in Step 3.

For example, if you kept the default (Caps Lock), set vPilot's PTT to Caps Lock as well. The Python server will simulate pressing this exact key when you hold the PTT button in the browser.

### Step 5: Start the Server

**With the desktop GUI** (recommended for most users):

```bash
python gui.py
```

**Headless mode** (no window, runs in the background):

```bash
python remote_vatsim.py
```

The console or GUI will display the URL to use for remote access, including your local IP address and port.

### Step 6: Connect from Your Browser

1. On your phone, tablet, or any other device, open a web browser.
2. Navigate to `http://<your-pc-ip>:8080` (the exact URL is shown when the server starts).
3. You will see a large PTT button.
4. **Press and hold** the button to transmit. Release to stop.

That is all there is to it. Your voice flows through VoIP into vPilot via the virtual cable, and your PTT command flows through WebSocket to the server which simulates the key press.

## Configuration

Settings are stored in `config.json`, created by the setup wizard. You can also edit it by hand:

```json
{
  "ptt_key": "caps_lock",
  "http_port": 8080,
  "ws_port": 8765
}
```

| Field       | Description                                      | Default      |
|-------------|--------------------------------------------------|--------------|
| `ptt_key`   | The key to simulate for PTT. Must match vPilot.  | `caps_lock`  |
| `http_port` | Port for the web-based PTT interface.             | `8080`       |
| `ws_port`   | Port for the WebSocket connection.                | `8765`       |

Common values for `ptt_key`: `caps_lock`, `scroll_lock`, `num_lock`, `f1` through `f12`, or any single letter/number key.

## Remote Access

### On your local network (LAN)

Use your PC's local IP address. You can find it by running `ipconfig` in a command prompt and looking for your IPv4 address (usually something like `192.168.x.x`).

Open `http://192.168.x.x:8080` on your remote device.

### Over the internet (WAN)

To access the PTT server from outside your local network, you have a few options:

- **Port forwarding** — Forward both `http_port` and `ws_port` on your router to your PC's local IP. Then use your public IP to connect.
- **VPN or tunnel** — Tools like Tailscale, WireGuard, or ngrok can expose your local server without opening ports on your router.

**Security note:** There is no authentication built in. Anyone who can reach the URL can trigger PTT on your VATSIM connection. If you expose this to the internet, consider placing it behind a VPN or a reverse proxy with authentication.

## Troubleshooting

**PTT key not working in vPilot**

- Make sure the PTT key configured in `config.json` matches exactly what is set in vPilot's PTT settings.
- Run the Python server as administrator if the key press is not being detected by vPilot.

**No audio coming through in vPilot**

- Verify that your VoIP app's output device is set to **CABLE Input**.
- Verify that vPilot's microphone is set to **CABLE Output**.
- Test the virtual cable by speaking in your VoIP app and checking the audio level in vPilot's mic meter.
- Make sure the VoIP app is not muted and the volume is turned up.

**Cannot connect from phone or remote device**

- Make sure your PC's firewall allows inbound connections on both ports (default: 8080 and 8765).
- Confirm the phone is on the same network as the PC (for LAN access).
- Try accessing the URL from another browser or device to rule out device-specific issues.

**WebSocket keeps disconnecting**

- The client automatically reconnects when the connection drops, so brief interruptions should recover on their own.
- If disconnects are frequent, check your network stability and ensure no firewall or antivirus is interfering with WebSocket traffic.

**VB-Cable not showing up as an audio device**

- Reboot your PC after installing VB-Cable.
- Re-run the VB-Cable installer as administrator.

## Tech Stack

- **Python** — core server runtime
- **asyncio** — asynchronous event loop for handling connections
- **websockets** — WebSocket server for real-time PTT communication
- **pynput** — simulates keyboard key presses for PTT
- **tkinter** — desktop GUI (built into Python, no extra install needed)

## License

MIT
