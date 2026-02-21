"""
Remote VATSIM PTT Controller - Core Server

Runs an HTTP server (serves web UI) and a WebSocket server (receives PTT commands)
to allow remote push-to-talk control of vPilot via OS-level key simulation.

Can be run standalone:
    python remote_vatsim.py

Or imported by gui.py for integrated desktop control.
"""

import asyncio
import json
import logging
import socket
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import websockets
from pynput.keyboard import Controller as KeyboardController, Key

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("remote_vatsim")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
WEB_DIR = BASE_DIR / "web"

DEFAULT_CONFIG = {
    "ptt_key": "caps_lock",
    "http_port": 8080,
    "ws_port": 8765,
}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config() -> dict:
    """Load configuration from config.json, falling back to defaults."""
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
        logger.info("Loaded config from %s", CONFIG_PATH)
    except FileNotFoundError:
        logger.warning("config.json not found, using defaults")
    except json.JSONDecodeError as exc:
        logger.error("Invalid config.json: %s — using defaults", exc)
    return config


# ---------------------------------------------------------------------------
# Key mapping & simulation
# ---------------------------------------------------------------------------

# Build a lookup table: lowercase string name -> pynput Key member
# This covers all Key.* attributes like caps_lock, ctrl_l, alt_l, shift, space, etc.
_KEY_MAP: dict[str, Key] = {}
for attr in dir(Key):
    if attr.startswith("_"):
        continue
    obj = getattr(Key, attr)
    if isinstance(obj, Key):
        _KEY_MAP[attr.lower()] = obj

_keyboard = KeyboardController()


def _resolve_key(key_name: str):
    """Resolve a string key name to a pynput key object.

    Supports:
      - Named special keys: 'caps_lock', 'ctrl_l', 'alt_l', 'shift', 'space', etc.
      - Single characters: 'b', 'v', '1', etc.
    """
    normalized = key_name.strip().lower()

    # Check special-key map first
    if normalized in _KEY_MAP:
        return _KEY_MAP[normalized]

    # Single character
    if len(normalized) == 1:
        return normalized

    # Try with underscores replaced by spaces and vice versa (convenience)
    alt = normalized.replace(" ", "_")
    if alt in _KEY_MAP:
        return _KEY_MAP[alt]

    raise ValueError(
        f"Unknown key name: '{key_name}'. "
        f"Valid special keys: {sorted(_KEY_MAP.keys())}. "
        f"Or use a single character like 'b'."
    )


def _press_key(key) -> None:
    """Press (hold down) a key."""
    try:
        _keyboard.press(key)
        logger.debug("Key pressed: %s", key)
    except Exception as exc:
        logger.error("Failed to press key %s: %s", key, exc)


def _release_key(key) -> None:
    """Release a key."""
    try:
        _keyboard.release(key)
        logger.debug("Key released: %s", key)
    except Exception as exc:
        logger.error("Failed to release key %s: %s", key, exc)


# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------

_ptt_state: bool = False
_clients: set = set()
_ptt_key = None  # resolved pynput key object, set at server start
_config: dict = {}

# Callbacks for GUI integration (called from asyncio thread)
_on_ptt_change: callable = None
_on_client_change: callable = None

# Server lifecycle
_ws_server = None
_http_server: HTTPServer | None = None
_http_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None
_server_thread: threading.Thread | None = None


def get_ptt_state() -> bool:
    """Return current PTT state (True = transmitting)."""
    return _ptt_state


def get_client_count() -> int:
    """Return number of connected WebSocket clients."""
    return len(_clients)


# ---------------------------------------------------------------------------
# WebSocket server
# ---------------------------------------------------------------------------


async def _broadcast(message: dict) -> None:
    """Send a JSON message to all connected clients."""
    if not _clients:
        return
    payload = json.dumps(message)
    # Use gather to send concurrently; discard individual failures
    await asyncio.gather(
        *(client.send(payload) for client in _clients),
        return_exceptions=True,
    )


async def _handle_client(websocket) -> None:
    """Handle a single WebSocket client connection."""
    global _ptt_state

    _clients.add(websocket)
    remote = websocket.remote_address
    logger.info("Client connected: %s:%s (%d total)", remote[0], remote[1], len(_clients))

    if _on_client_change:
        _on_client_change(len(_clients))

    try:
        # Greet the new client
        await websocket.send(json.dumps({"status": "connected"}))

        # If PTT is currently on, let the new client know
        if _ptt_state:
            await websocket.send(json.dumps({"status": "ptt_on"}))

        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from %s: %s", remote, raw_message)
                continue

            action = message.get("action")
            state = message.get("state")

            if action == "ptt":
                if state == "on" and not _ptt_state:
                    _ptt_state = True
                    _press_key(_ptt_key)
                    logger.info("PTT ON  (from %s:%s)", remote[0], remote[1])
                    await _broadcast({"status": "ptt_on"})
                    if _on_ptt_change:
                        _on_ptt_change(True)

                elif state == "off" and _ptt_state:
                    _ptt_state = False
                    _release_key(_ptt_key)
                    logger.info("PTT OFF (from %s:%s)", remote[0], remote[1])
                    await _broadcast({"status": "ptt_off"})
                    if _on_ptt_change:
                        _on_ptt_change(False)
                else:
                    logger.debug("PTT state already %s, ignoring", state)
            else:
                logger.warning("Unknown action from %s: %s", remote, action)

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as exc:
        logger.error("Error handling client %s: %s", remote, exc)
    finally:
        _clients.discard(websocket)
        logger.info("Client disconnected: %s:%s (%d remaining)", remote[0], remote[1], len(_clients))

        if _on_client_change:
            _on_client_change(len(_clients))

        # Safety: if the disconnecting client was holding PTT, release it
        if _ptt_state and len(_clients) == 0:
            _ptt_state = False
            _release_key(_ptt_key)
            logger.info("PTT released (last client disconnected)")
            if _on_ptt_change:
                _on_ptt_change(False)


# ---------------------------------------------------------------------------
# HTTP server (serves web UI)
# ---------------------------------------------------------------------------


class _QuietHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP handler that serves from the web/ directory and suppresses logs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        # Redirect root to index.html with the WS port so the client auto-connects
        if self.path == "/":
            ws_port = _config.get("ws_port", 8765)
            self.send_response(302)
            self.send_header("Location", f"/index.html?ws_port={ws_port}")
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format, *args):
        # Route through our logger instead of stderr
        logger.debug("HTTP: " + format % args)


def _start_http_server(port: int) -> HTTPServer:
    """Create and return an HTTP server bound to 0.0.0.0:port."""
    server = HTTPServer(("0.0.0.0", port), _QuietHTTPHandler)
    server.timeout = 0.5
    return server


# ---------------------------------------------------------------------------
# simulate_ptt (for GUI / external use)
# ---------------------------------------------------------------------------


def simulate_ptt(state: bool) -> None:
    """Manually trigger PTT on/off. Safe to call from any thread.

    If the WebSocket event loop is running, schedules the broadcast there.
    Otherwise just presses/releases the key directly.
    """
    global _ptt_state

    if state and not _ptt_state:
        _ptt_state = True
        _press_key(_ptt_key)
        logger.info("PTT ON  (local)")
        if _on_ptt_change:
            _on_ptt_change(True)
        if _loop and _loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast({"status": "ptt_on"}), _loop)

    elif not state and _ptt_state:
        _ptt_state = False
        _release_key(_ptt_key)
        logger.info("PTT OFF (local)")
        if _on_ptt_change:
            _on_ptt_change(False)
        if _loop and _loop.is_running():
            asyncio.run_coroutine_threadsafe(_broadcast({"status": "ptt_off"}), _loop)


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


def _get_local_ip() -> str:
    """Best-effort detection of the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


async def _run_ws_server(ws_port: int) -> None:
    """Run the WebSocket server until cancelled."""
    global _ws_server
    _ws_server = await websockets.serve(
        _handle_client,
        "0.0.0.0",
        ws_port,
    )
    logger.info("WebSocket server listening on 0.0.0.0:%d", ws_port)
    await _ws_server.wait_closed()


def _run_asyncio_loop(ws_port: int) -> None:
    """Entry point for the asyncio server thread."""
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    try:
        _loop.run_until_complete(_run_ws_server(ws_port))
    except asyncio.CancelledError:
        pass
    finally:
        _loop.run_until_complete(_loop.shutdown_asyncgens())
        _loop.close()
        _loop = None


def start_server(
    on_ptt_change: callable = None,
    on_client_change: callable = None,
) -> None:
    """Start both the HTTP and WebSocket servers.

    Args:
        on_ptt_change: Optional callback(bool) invoked when PTT state changes.
        on_client_change: Optional callback(int) invoked when client count changes.
    """
    global _on_ptt_change, _on_client_change, _config, _ptt_key
    global _http_server, _http_thread, _server_thread

    _on_ptt_change = on_ptt_change
    _on_client_change = on_client_change

    _config = load_config()
    _ptt_key = _resolve_key(_config["ptt_key"])
    http_port = _config["http_port"]
    ws_port = _config["ws_port"]
    local_ip = _get_local_ip()

    logger.info("PTT key: %s -> %s", _config["ptt_key"], _ptt_key)

    # --- HTTP server (daemon thread) ---
    if not WEB_DIR.is_dir():
        logger.warning("web/ directory not found at %s — HTTP server will 404", WEB_DIR)

    _http_server = _start_http_server(http_port)
    _http_thread = threading.Thread(
        target=_http_server.serve_forever,
        name="http-server",
        daemon=True,
    )
    _http_thread.start()
    logger.info("HTTP server listening on 0.0.0.0:%d", http_port)

    # --- WebSocket server (own asyncio loop in a thread) ---
    _server_thread = threading.Thread(
        target=_run_asyncio_loop,
        args=(ws_port,),
        name="ws-server",
        daemon=True,
    )
    _server_thread.start()

    # --- Banner ---
    banner = (
        "\n"
        "============================================\n"
        "  Remote VATSIM PTT Controller\n"
        "============================================\n"
        f"  Web UI:     http://{local_ip}:{http_port}\n"
        f"  WebSocket:  ws://{local_ip}:{ws_port}\n"
        f"  PTT Key:    {_config['ptt_key']}\n"
        "============================================\n"
        "  Open the Web UI URL on your phone/tablet\n"
        "  Press Ctrl+C to stop\n"
        "============================================\n"
    )
    print(banner)


def stop_server() -> None:
    """Stop both servers gracefully."""
    global _http_server, _http_thread, _ws_server, _server_thread, _loop, _ptt_state

    # Release PTT if it's held
    if _ptt_state:
        _ptt_state = False
        _release_key(_ptt_key)
        logger.info("PTT released (server stopping)")
        if _on_ptt_change:
            _on_ptt_change(False)

    # Stop HTTP server
    if _http_server:
        _http_server.shutdown()
        _http_server = None
        logger.info("HTTP server stopped")

    # Stop WebSocket server
    if _ws_server and _loop and _loop.is_running():
        async def _shutdown_ws():
            _ws_server.close()
            await _ws_server.wait_closed()

        future = asyncio.run_coroutine_threadsafe(_shutdown_ws(), _loop)
        try:
            future.result(timeout=5)
        except Exception as exc:
            logger.warning("Error stopping WebSocket server: %s", exc)
        logger.info("WebSocket server stopped")

    # Wait for threads to finish
    if _server_thread and _server_thread.is_alive():
        _server_thread.join(timeout=3)
    if _http_thread and _http_thread.is_alive():
        _http_thread.join(timeout=3)

    _http_thread = None
    _server_thread = None

    # Clear client set
    _clients.clear()

    logger.info("All servers stopped")


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the server standalone (blocking)."""
    start_server()
    try:
        # Block the main thread; servers run in daemon threads
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        stop_server()
        logger.info("Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
