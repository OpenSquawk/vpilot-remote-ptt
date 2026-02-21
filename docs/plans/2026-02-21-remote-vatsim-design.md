# Remote VATSIM PTT Controller — Design Document

## Problem

You're a VATSIM pilot or ATC. You want to let someone (or yourself) transmit on VATSIM from a remote location — e.g., via a phone call, Discord, or any VoIP app. The remote person speaks, and their voice gets transmitted through vPilot as if they were sitting at the PC.

## Solution

Two pieces working together:

1. **Audio Routing**: VB-Audio Virtual Cable routes the VoIP app's audio output into a virtual microphone that vPilot uses as its mic input. This runs permanently — no code needed.

2. **PTT Controller**: A Python script that runs an HTTP + WebSocket server. Anyone with the URL can open a web page with a big PTT button. Pressing the button sends a WebSocket message, and the script simulates the configured PTT key press on the OS level. vPilot picks up the key press and transmits.

## Architecture

```
Remote Person (phone/browser)
        │
        │ WebSocket
        ▼
┌─ Windows PC ─────────────────────────────┐
│                                          │
│  VoIP App ──▶ VB-Cable ──▶ vPilot (mic)  │
│                                          │
│  remote_vatsim.py                        │
│   ├─ HTTP Server  → serves web UI        │
│   ├─ WebSocket    → receives PTT cmds    │
│   ├─ Key Simulator→ presses PTT key      │
│   └─ Tkinter GUI  → local status/control │
│                                          │
└──────────────────────────────────────────┘
```

## Components

### remote_vatsim.py
- HTTP server (default :8080) serves web/index.html
- WebSocket server (default :8765) receives JSON PTT commands
- pynput-based key simulator for OS-level key presses
- Config loaded from config.json

### web/index.html
- Large touch-friendly PTT button (hold to talk)
- Mouse + touch support
- Visual feedback (color change on press)
- Connection status indicator
- Auto-reconnect

### gui.py
- Tkinter-based mini desktop GUI
- Shows PTT status, connected clients, server status
- Start/stop server button
- System tray optional

### setup.py
- Interactive CLI wizard
- Checks Python, installs deps, detects VB-Cable
- Configures PTT key and ports
- Writes config.json

### config.json
```json
{
  "ptt_key": "caps_lock",
  "http_port": 8080,
  "ws_port": 8765
}
```

## WebSocket Protocol

```
Client → Server: {"action": "ptt", "state": "on"}
Client → Server: {"action": "ptt", "state": "off"}
Server → Client: {"status": "ptt_on"}
Server → Client: {"status": "ptt_off"}
Server → Client: {"status": "connected"}
```

## File Structure

```
remote-vatsim/
├── README.md
├── requirements.txt
├── config.json
├── setup.py
├── remote_vatsim.py
├── gui.py
└── web/
    └── index.html
```

## Decisions

- **VB-Cable over Python audio routing**: Zero latency, zero code, battle-tested.
- **pynput over keyboard lib**: pynput works without admin rights for key simulation.
- **Python all-in-one over Node+Python split**: Single process, simpler deployment.
- **Tkinter for GUI**: Ships with Python, no extra dependencies.
