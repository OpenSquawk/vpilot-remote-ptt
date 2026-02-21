"""
Remote VATSIM PTT Controller - Desktop GUI

Tkinter-based desktop GUI for controlling the Remote VATSIM PTT server.
Provides server start/stop, PTT status monitoring, client count, and local PTT testing.

Usage:
    python gui.py
"""

import socket
import threading
import tkinter as tk
from tkinter import font as tkfont

import remote_vatsim


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG_DARK = "#1e1e1e"
BG_SECTION = "#2a2a2a"
BG_BUTTON = "#3a3a3a"
BG_BUTTON_HOVER = "#4a4a4a"
FG_TEXT = "#e0e0e0"
FG_DIM = "#888888"
FG_GREEN = "#4caf50"
FG_RED = "#f44336"
FG_ORANGE = "#ff9800"
FG_BLUE = "#64b5f6"
ACCENT = "#5c9ded"


def _get_local_ip() -> str:
    """Return the machine's LAN IP address (best guess)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class RemoteVatsimGUI:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Remote VATSIM Controller")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_DARK)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # State
        self.server_running = False
        self.ptt_active = False
        self.client_count = 0
        self.config: dict = {}

        # Fonts
        self.font_title = tkfont.Font(family="Segoe UI", size=18, weight="bold")
        self.font_heading = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.font_normal = tkfont.Font(family="Segoe UI", size=10)
        self.font_small = tkfont.Font(family="Segoe UI", size=9)
        self.font_mono = tkfont.Font(family="Consolas", size=9)
        self.font_ptt_label = tkfont.Font(family="Segoe UI", size=13, weight="bold")

        self._build_ui()
        self._load_config()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        """Construct all UI widgets."""

        # --- Header ---
        header_frame = tk.Frame(self.root, bg=BG_DARK)
        header_frame.pack(fill="x", padx=16, pady=(14, 4))

        tk.Label(
            header_frame,
            text="Remote VATSIM",
            font=self.font_title,
            fg=ACCENT,
            bg=BG_DARK,
        ).pack(anchor="w")

        # --- Server status section ---
        srv_frame = tk.Frame(self.root, bg=BG_SECTION, highlightbackground="#333",
                             highlightthickness=1)
        srv_frame.pack(fill="x", padx=16, pady=(8, 4))

        srv_top = tk.Frame(srv_frame, bg=BG_SECTION)
        srv_top.pack(fill="x", padx=12, pady=(10, 2))

        self.status_label = tk.Label(
            srv_top,
            text="Server: Stopped",
            font=self.font_heading,
            fg=FG_RED,
            bg=BG_SECTION,
        )
        self.status_label.pack(side="left")

        self.toggle_btn = tk.Button(
            srv_top,
            text="Start Server",
            font=self.font_normal,
            bg=FG_GREEN,
            fg="#ffffff",
            activebackground="#388e3c",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=2,
            cursor="hand2",
            command=self._toggle_server,
        )
        self.toggle_btn.pack(side="right")

        # URL labels (hidden until server starts)
        self.url_frame = tk.Frame(srv_frame, bg=BG_SECTION)
        self.url_frame.pack(fill="x", padx=12, pady=(2, 10))

        self.http_url_label = tk.Label(
            self.url_frame,
            text="",
            font=self.font_mono,
            fg=FG_BLUE,
            bg=BG_SECTION,
            cursor="hand2",
        )
        self.http_url_label.pack(anchor="w")

        self.ws_url_label = tk.Label(
            self.url_frame,
            text="",
            font=self.font_mono,
            fg=FG_DIM,
            bg=BG_SECTION,
        )
        self.ws_url_label.pack(anchor="w")

        # --- PTT status section ---
        ptt_frame = tk.Frame(self.root, bg=BG_SECTION, highlightbackground="#333",
                             highlightthickness=1)
        ptt_frame.pack(fill="x", padx=16, pady=4)

        ptt_inner = tk.Frame(ptt_frame, bg=BG_SECTION)
        ptt_inner.pack(padx=12, pady=12)

        self.ptt_canvas = tk.Canvas(
            ptt_inner, width=48, height=48, bg=BG_SECTION, highlightthickness=0
        )
        self.ptt_canvas.pack(side="left", padx=(0, 10))
        self.ptt_circle = self.ptt_canvas.create_oval(
            4, 4, 44, 44, fill="#555555", outline="#666666", width=2
        )

        self.ptt_label = tk.Label(
            ptt_inner,
            text="PTT: OFF",
            font=self.font_ptt_label,
            fg=FG_DIM,
            bg=BG_SECTION,
        )
        self.ptt_label.pack(side="left")

        # --- Clients section ---
        clients_frame = tk.Frame(self.root, bg=BG_SECTION, highlightbackground="#333",
                                 highlightthickness=1)
        clients_frame.pack(fill="x", padx=16, pady=4)

        self.clients_label = tk.Label(
            clients_frame,
            text="Connected Clients: 0",
            font=self.font_heading,
            fg=FG_TEXT,
            bg=BG_SECTION,
        )
        self.clients_label.pack(padx=12, pady=10, anchor="w")

        # --- Configuration section ---
        config_frame = tk.Frame(self.root, bg=BG_SECTION, highlightbackground="#333",
                                highlightthickness=1)
        config_frame.pack(fill="x", padx=16, pady=4)

        config_title = tk.Label(
            config_frame,
            text="Configuration",
            font=self.font_heading,
            fg=FG_TEXT,
            bg=BG_SECTION,
        )
        config_title.pack(padx=12, pady=(10, 4), anchor="w")

        config_grid = tk.Frame(config_frame, bg=BG_SECTION)
        config_grid.pack(fill="x", padx=12, pady=(0, 10))

        labels = ["PTT Key:", "HTTP Port:", "WS Port:"]
        self.config_values: list[tk.Label] = []
        for i, text in enumerate(labels):
            tk.Label(
                config_grid, text=text, font=self.font_small, fg=FG_DIM, bg=BG_SECTION
            ).grid(row=i, column=0, sticky="w", padx=(0, 8), pady=1)
            val_label = tk.Label(
                config_grid, text="--", font=self.font_mono, fg=FG_TEXT, bg=BG_SECTION
            )
            val_label.grid(row=i, column=1, sticky="w", pady=1)
            self.config_values.append(val_label)

        # --- Local PTT button ---
        ptt_btn_frame = tk.Frame(self.root, bg=BG_DARK)
        ptt_btn_frame.pack(fill="x", padx=16, pady=(8, 14))

        self.local_ptt_btn = tk.Button(
            ptt_btn_frame,
            text="Hold to Talk (Local PTT)",
            font=self.font_normal,
            bg=BG_BUTTON,
            fg=FG_TEXT,
            activebackground=FG_RED,
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
            pady=8,
            cursor="hand2",
        )
        self.local_ptt_btn.pack(fill="x")
        self.local_ptt_btn.bind("<ButtonPress-1>", self._local_ptt_press)
        self.local_ptt_btn.bind("<ButtonRelease-1>", self._local_ptt_release)

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load configuration from remote_vatsim and populate labels."""
        self.config = remote_vatsim.load_config()
        ptt_key = self.config.get("ptt_key", "caps_lock")
        http_port = self.config.get("http_port", 8080)
        ws_port = self.config.get("ws_port", 8765)

        self.config_values[0].configure(text=ptt_key)
        self.config_values[1].configure(text=str(http_port))
        self.config_values[2].configure(text=str(ws_port))

    # ------------------------------------------------------------------
    # Server control
    # ------------------------------------------------------------------

    def _toggle_server(self) -> None:
        if self.server_running:
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self) -> None:
        """Start the PTT server in a daemon thread."""
        def _run() -> None:
            remote_vatsim.start_server(
                on_ptt_change=self._on_ptt_change,
                on_client_change=self._on_client_change,
            )

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        self.server_running = True
        self._update_server_status()

    def _stop_server(self) -> None:
        """Stop the PTT server and update UI."""
        remote_vatsim.stop_server()
        self.server_running = False
        self.ptt_active = False
        self.client_count = 0
        self._update_server_status()
        self._update_ptt_status()
        self._update_client_count()

    def _update_server_status(self) -> None:
        """Refresh all server-related UI elements."""
        if self.server_running:
            self.status_label.configure(text="Server: Running", fg=FG_GREEN)
            self.toggle_btn.configure(
                text="Stop Server", bg=FG_RED, activebackground="#c62828"
            )
            ip = _get_local_ip()
            http_port = self.config.get("http_port", 8080)
            ws_port = self.config.get("ws_port", 8765)
            self.http_url_label.configure(text=f"HTTP:  http://{ip}:{http_port}")
            self.ws_url_label.configure(text=f"WS:    ws://{ip}:{ws_port}")
        else:
            self.status_label.configure(text="Server: Stopped", fg=FG_RED)
            self.toggle_btn.configure(
                text="Start Server", bg=FG_GREEN, activebackground="#388e3c"
            )
            self.http_url_label.configure(text="")
            self.ws_url_label.configure(text="")

    # ------------------------------------------------------------------
    # PTT callbacks (called from server thread)
    # ------------------------------------------------------------------

    def _on_ptt_change(self, state: bool) -> None:
        """Called by remote_vatsim when PTT state changes. Thread-safe."""
        self.root.after(0, self._apply_ptt_state, state)

    def _apply_ptt_state(self, state: bool) -> None:
        self.ptt_active = state
        self._update_ptt_status()

    def _update_ptt_status(self) -> None:
        if self.ptt_active:
            self.ptt_canvas.itemconfigure(
                self.ptt_circle, fill=FG_RED, outline="#ff6659"
            )
            self.ptt_label.configure(text="PTT: ON AIR", fg=FG_RED)
        else:
            self.ptt_canvas.itemconfigure(
                self.ptt_circle, fill="#555555", outline="#666666"
            )
            self.ptt_label.configure(text="PTT: OFF", fg=FG_DIM)

    # ------------------------------------------------------------------
    # Client count callback (called from server thread)
    # ------------------------------------------------------------------

    def _on_client_change(self, count: int) -> None:
        """Called by remote_vatsim when the connected client count changes. Thread-safe."""
        self.root.after(0, self._apply_client_count, count)

    def _apply_client_count(self, count: int) -> None:
        self.client_count = count
        self._update_client_count()

    def _update_client_count(self) -> None:
        self.clients_label.configure(
            text=f"Connected Clients: {self.client_count}"
        )

    # ------------------------------------------------------------------
    # Local PTT button
    # ------------------------------------------------------------------

    def _local_ptt_press(self, _event: tk.Event) -> None:
        if self.server_running:
            remote_vatsim.simulate_ptt(True)

    def _local_ptt_release(self, _event: tk.Event) -> None:
        if self.server_running:
            remote_vatsim.simulate_ptt(False)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        """Clean up and exit."""
        if self.server_running:
            remote_vatsim.stop_server()
        self.root.destroy()

    def run(self) -> None:
        """Enter the Tkinter main loop."""
        self.root.mainloop()


def main() -> None:
    app = RemoteVatsimGUI()
    app.run()


if __name__ == "__main__":
    main()
