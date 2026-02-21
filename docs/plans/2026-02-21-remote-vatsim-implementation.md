# Remote VATSIM PTT Controller — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python app that lets anyone trigger vPilot PTT via a web button over WebSocket, with a desktop GUI for local control.

**Architecture:** Single Python process runs HTTP server (serves web UI), WebSocket server (receives PTT commands), and key simulator (pynput). Tkinter GUI for local status/control. VB-Audio Virtual Cable handles audio routing (no code needed).

**Tech Stack:** Python 3.8+, asyncio, websockets, pynput, tkinter, http.server

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.json`
- Create: `.gitignore`

**Step 1: Create requirements.txt**

```
websockets>=12.0
pynput>=1.7.6
```

**Step 2: Create config.json**

```json
{
  "ptt_key": "caps_lock",
  "http_port": 8080,
  "ws_port": 8765
}
```

**Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.venv/
venv/
```

**Step 4: Commit**

```bash
git add requirements.txt config.json .gitignore
git commit -m "chore: project scaffolding"
```

---

### Task 2: Core PTT Server (`remote_vatsim.py`)

**Files:**
- Create: `remote_vatsim.py`

**Step 1: Implement config loader**

Load `config.json`, provide defaults if missing.

**Step 2: Implement key simulator**

Use `pynput.keyboard.Controller` to press/release the configured PTT key. Map string key names to pynput Key objects.

**Step 3: Implement WebSocket server**

asyncio-based WebSocket server. On `{"action": "ptt", "state": "on"}` → press key. On `"off"` → release key. Broadcast status back to all clients. Track connected clients.

**Step 4: Implement HTTP server**

Serve files from `web/` directory on the HTTP port. Threaded so it runs alongside asyncio.

**Step 5: Implement main entry point**

Start HTTP server thread + asyncio WebSocket server. Print URLs on startup.

**Step 6: Commit**

```bash
git add remote_vatsim.py
git commit -m "feat: core PTT server with HTTP + WebSocket + key simulation"
```

---

### Task 3: Web UI (`web/index.html`)

**Files:**
- Create: `web/index.html`

**Step 1: Build HTML/CSS/JS single-file app**

- Large centered PTT button, mobile-friendly
- mousedown/mouseup + touchstart/touchend handlers
- WebSocket connection with auto-reconnect
- Visual states: disconnected (gray), connected (green), transmitting (red)
- Status text showing connection state
- Responsive layout

**Step 2: Commit**

```bash
git add web/index.html
git commit -m "feat: web PTT UI with touch support and auto-reconnect"
```

---

### Task 4: Desktop GUI (`gui.py`)

**Files:**
- Create: `gui.py`

**Step 1: Build Tkinter GUI**

- Window title "Remote VATSIM Controller"
- Server status (running/stopped)
- Start/Stop server button
- PTT status indicator (on/off with color)
- Connected clients count
- PTT key display + edit
- Port display
- PTT button in GUI too (for local testing)
- Runs the server in a background thread

**Step 2: Commit**

```bash
git add gui.py
git commit -m "feat: tkinter desktop GUI with server control and PTT status"
```

---

### Task 5: Setup Wizard (`setup.py`)

**Files:**
- Create: `setup.py`

**Step 1: Build interactive CLI wizard**

- Check Python version (3.8+)
- Create venv and install dependencies
- Check/prompt for VB-Cable installation
- Configure PTT key interactively
- Configure ports
- Write config.json
- Print summary and next steps

**Step 2: Commit**

```bash
git add setup.py
git commit -m "feat: interactive setup wizard"
```

---

### Task 6: README

**Files:**
- Create: `README.md`

**Step 1: Write comprehensive README**

- Problem explanation
- How it works (architecture diagram)
- Prerequisites
- Quick Start (3 steps)
- Detailed Setup Guide
- Configuration Reference
- Troubleshooting
- FAQ

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: comprehensive README with setup guide"
```

---

### Task 7: Final Integration & Push

**Step 1: Verify all files present and consistent**
**Step 2: Final commit if needed**
**Step 3: Push to remote**
