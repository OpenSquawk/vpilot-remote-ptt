#!/usr/bin/env python3
"""
Remote VATSIM PTT Controller - Interactive Setup Wizard
Guides you through installing dependencies, detecting VB-Cable,
configuring the PTT key and ports, and writing config.json.
"""

import sys
import os
import json
import subprocess
import socket
import platform
import shutil

# ---------------------------------------------------------------------------
# ANSI colour helpers (with graceful fallback on terminals that don't support them)
# ---------------------------------------------------------------------------

def _supports_color():
    """Return True if the terminal probably supports ANSI escape codes."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if platform.system() == "Windows":
        # Windows 10 1511+ supports ANSI in conhost; WT always does.
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable ANSI processing on stdout
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return os.environ.get("WT_SESSION") is not None
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

USE_COLOR = _supports_color()

def _c(code, text):
    if USE_COLOR:
        return f"\033[{code}m{text}\033[0m"
    return text

def bold(t):      return _c("1", t)
def green(t):     return _c("32", t)
def red(t):       return _c("31", t)
def yellow(t):    return _c("33", t)
def cyan(t):      return _c("36", t)
def magenta(t):   return _c("35", t)
def dim(t):       return _c("2", t)
def bold_green(t):  return _c("1;32", t)
def bold_cyan(t):   return _c("1;36", t)
def bold_red(t):    return _c("1;31", t)
def bold_yellow(t): return _c("1;33", t)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOTAL_STEPS = 8
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def step_header(num, title):
    bar = bold_cyan(f"[{num}/{TOTAL_STEPS}]")
    print(f"\n{'=' * 60}")
    print(f"  {bar}  {bold(title)}")
    print(f"{'=' * 60}")

def success(msg):
    print(f"  {bold_green('[OK]')} {msg}")

def warn(msg):
    print(f"  {bold_yellow('[!!]')} {msg}")

def error(msg):
    print(f"  {bold_red('[ERR]')} {msg}")

def info(msg):
    print(f"  {cyan('[i]')} {msg}")

def prompt(msg, default=None):
    """Prompt the user for input. Press Enter to accept the default."""
    if default is not None:
        raw = input(f"  {cyan('>')} {msg} [{bold(str(default))}]: ").strip()
        return raw if raw else str(default)
    return input(f"  {cyan('>')} {msg}: ").strip()

def confirm(msg, default_yes=True):
    """Yes/No prompt. Returns bool."""
    hint = "Y/n" if default_yes else "y/N"
    raw = input(f"  {cyan('>')} {msg} ({hint}): ").strip().lower()
    if not raw:
        return default_yes
    return raw in ("y", "yes")

def cls():
    """Clear the terminal screen (Windows-aware)."""
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

# ---------------------------------------------------------------------------
# Step 1 - Welcome
# ---------------------------------------------------------------------------

def welcome():
    step_header(1, "Welcome")
    banner = r"""
     ____                      _      __     ___  _____ ___ __  __
    |  _ \ ___ _ __ ___   ___ | |_ ___\ \   / / \|_   _/ __|  \/  |
    | |_) / _ \ '_ ` _ \ / _ \| __/ _ \\ \ / / _ \ | | \__ \ |\/| |
    |  _ <  __/ | | | | | (_) | ||  __/ \ V / ___ \| | |___/ |  | |
    |_| \_\___|_| |_| |_|\___/ \__\___|  \_/_/   \_\_| |____/|_|  |_|

                     PTT Controller  -  Setup Wizard
    """
    print(bold_cyan(banner))
    print("  This wizard will help you set up the Remote VATSIM PTT Controller.")
    print("  It lets anyone trigger your vPilot PTT via a web button so a remote")
    print("  person can transmit on VATSIM through your PC.\n")
    print(f"  {dim('Press Enter to accept defaults shown in [brackets].')}")
    print(f"  {dim('Press Ctrl+C at any time to abort.')}\n")
    input(f"  {cyan('>')} Press {bold('Enter')} to begin...")

# ---------------------------------------------------------------------------
# Step 2 - Check Python version
# ---------------------------------------------------------------------------

def check_python():
    step_header(2, "Check Python Version")
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    info(f"Detected Python {bold(ver_str)} ({sys.executable})")

    if v < (3, 8):
        error(f"Python 3.8 or higher is required. You have {ver_str}.")
        print()
        print("  Please install a newer version of Python from:")
        print(f"  {bold('https://www.python.org/downloads/')}")
        print()
        sys.exit(1)

    success(f"Python {ver_str} meets the minimum requirement (3.8+).")

# ---------------------------------------------------------------------------
# Step 3 - Install dependencies
# ---------------------------------------------------------------------------

def install_dependencies():
    step_header(3, "Install Dependencies")

    req_file = os.path.join(BASE_DIR, "requirements.txt")
    if not os.path.isfile(req_file):
        error(f"requirements.txt not found at {req_file}")
        error("Cannot install dependencies. Please make sure requirements.txt exists.")
        sys.exit(1)

    info("Dependencies needed: websockets, pynput")
    print()

    use_venv = confirm("Create a virtual environment (.venv)? (recommended)", default_yes=True)

    pip_cmd = None
    python_cmd = sys.executable

    if use_venv:
        venv_dir = os.path.join(BASE_DIR, ".venv")
        if os.path.isdir(venv_dir):
            info(f"Virtual environment already exists at {venv_dir}")
            recreate = confirm("Recreate it from scratch?", default_yes=False)
            if recreate:
                info("Removing existing virtual environment...")
                shutil.rmtree(venv_dir)
            else:
                info("Reusing existing virtual environment.")
        if not os.path.isdir(venv_dir):
            info("Creating virtual environment...")
            result = subprocess.run(
                [python_cmd, "-m", "venv", venv_dir],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                error("Failed to create virtual environment:")
                print(f"    {result.stderr.strip()}")
                sys.exit(1)
            success("Virtual environment created.")

        # Determine pip path inside the venv
        if platform.system() == "Windows":
            pip_cmd = os.path.join(venv_dir, "Scripts", "pip.exe")
            python_in_venv = os.path.join(venv_dir, "Scripts", "python.exe")
        else:
            pip_cmd = os.path.join(venv_dir, "bin", "pip")
            python_in_venv = os.path.join(venv_dir, "bin", "python")

        if not os.path.isfile(pip_cmd):
            # Fallback: use python -m pip
            pip_cmd = None
    else:
        info("Installing globally using current Python interpreter.")

    # Build the install command
    if pip_cmd:
        cmd = [pip_cmd, "install", "-r", req_file]
    elif use_venv:
        cmd = [python_in_venv, "-m", "pip", "install", "-r", req_file]
    else:
        cmd = [python_cmd, "-m", "pip", "install", "-r", req_file]

    info(f"Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error("pip install failed:")
        for line in result.stderr.strip().splitlines():
            print(f"    {line}")
        print()
        error("Please resolve the error above and re-run setup.")
        sys.exit(1)

    # Show installed packages briefly
    for line in result.stdout.strip().splitlines():
        lowered = line.lower()
        if "successfully" in lowered or "requirement already" in lowered or "installing" in lowered:
            print(f"    {line}")

    success("All dependencies installed.")

    if use_venv:
        print()
        if platform.system() == "Windows":
            activate_hint = r".venv\Scripts\activate"
        else:
            activate_hint = "source .venv/bin/activate"
        info(f"Activate the venv before running the app:")
        print(f"    {bold(activate_hint)}")

# ---------------------------------------------------------------------------
# Step 4 - Check VB-Audio Virtual Cable
# ---------------------------------------------------------------------------

def check_vb_cable():
    step_header(4, "Check VB-Audio Virtual Cable")

    detected = None  # None = unknown, True = found, False = not found

    if platform.system() == "Windows":
        # Strategy 1: Check the Windows registry for VB-Cable driver
        try:
            import winreg
            search_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hive, base_key in search_paths:
                try:
                    key = winreg.OpenKey(hive, base_key)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            subkey = winreg.OpenKey(key, subkey_name)
                            try:
                                display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                                if "vb-audio" in display_name.lower() or "vb-cable" in display_name.lower():
                                    detected = True
                                    break
                            except FileNotFoundError:
                                pass
                            finally:
                                winreg.CloseKey(subkey)
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                    if detected:
                        break
                except OSError:
                    continue
        except ImportError:
            pass

        # Strategy 2: Look for the driver DLL
        if detected is None:
            vb_paths = [
                os.path.join(os.environ.get("PROGRAMFILES", ""), "VB", "CABLE"),
                os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "VB", "CABLE"),
                os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "vbcable.dll"),
            ]
            for p in vb_paths:
                if os.path.exists(p):
                    detected = True
                    break

        # Strategy 3: Check audio device names via PowerShell
        if detected is None:
            try:
                ps = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        "Get-AudioDevice -List 2>$null | Select-Object -ExpandProperty Name; "
                        "if ($LASTEXITCODE) { "
                        "  Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Name "
                        "}"
                    ],
                    capture_output=True, text=True, timeout=10,
                )
                output = ps.stdout.lower()
                if "cable" in output and "vb" in output:
                    detected = True
                elif ps.returncode == 0 and output.strip():
                    detected = False
            except Exception:
                pass
    else:
        # Non-Windows: skip detection
        info("VB-Cable detection is only available on Windows.")
        info("Skipping this check on your platform.")
        detected = None

    # Report results
    if detected is True:
        success("VB-Audio Virtual Cable detected on this system!")
    elif detected is False:
        warn("VB-Audio Virtual Cable was NOT detected.")
        print()
        print("  VB-Cable is required to route audio from your VoIP app")
        print("  (phone call, Discord, etc.) into vPilot's microphone input.")
        print()
        print(f"  Download it free from: {bold('https://vb-audio.com/Cable/')}")
        print()
        if confirm("Open the download page in your browser?", default_yes=True):
            _open_url("https://vb-audio.com/Cable/")
        print()
        info("After installing VB-Cable, restart this wizard or continue now.")
        input(f"  {cyan('>')} Press Enter to continue...")
    else:
        # Could not detect either way
        info("Could not automatically detect VB-Cable on this system.")
        has_it = confirm("Do you already have VB-Audio Virtual Cable installed?", default_yes=False)
        if has_it:
            success("Great! Continuing with setup.")
        else:
            print()
            print("  VB-Cable is required to route audio from your VoIP app")
            print("  (phone call, Discord, etc.) into vPilot's microphone input.")
            print()
            print(f"  Download it free from: {bold('https://vb-audio.com/Cable/')}")
            print()
            if confirm("Open the download page in your browser?", default_yes=True):
                _open_url("https://vb-audio.com/Cable/")
            print()
            info("You can install VB-Cable later. Continuing with setup...")
            input(f"  {cyan('>')} Press Enter to continue...")


def _open_url(url):
    """Best-effort open a URL in the default browser."""
    try:
        import webbrowser
        webbrowser.open(url)
        info("Opened in your default browser.")
    except Exception:
        warn("Could not open the browser automatically.")

# ---------------------------------------------------------------------------
# Step 5 - Configure PTT key
# ---------------------------------------------------------------------------

# Keys supported by pynput (common choices for PTT)
SUPPORTED_KEYS = {
    # Special keys (pynput.keyboard.Key.*)
    "caps_lock":    "Caps Lock",
    "scroll_lock":  "Scroll Lock",
    "pause":        "Pause / Break",
    "insert":       "Insert",
    "home":         "Home",
    "end":          "End",
    "page_up":      "Page Up",
    "page_down":    "Page Down",
    "num_lock":     "Num Lock",
    "f13":          "F13",
    "f14":          "F14",
    "f15":          "F15",
    "f16":          "F16",
    "f17":          "F17",
    "f18":          "F18",
    "f19":          "F19",
    "f20":          "F20",
    # Function keys
    "f1": "F1", "f2": "F2", "f3": "F3", "f4": "F4",
    "f5": "F5", "f6": "F6", "f7": "F7", "f8": "F8",
    "f9": "F9", "f10": "F10", "f11": "F11", "f12": "F12",
    # Modifier-ish
    "ctrl_l":   "Left Ctrl",
    "ctrl_r":   "Right Ctrl",
    "alt_l":    "Left Alt",
    "alt_r":    "Right Alt",
    "shift_l":  "Left Shift",
    "shift_r":  "Right Shift",
}

QUICK_OPTIONS = [
    ("caps_lock",   "Caps Lock (recommended, rarely used in sims)"),
    ("scroll_lock", "Scroll Lock"),
    ("pause",       "Pause / Break"),
    ("f13",         "F13 (if your keyboard has it)"),
    ("insert",      "Insert"),
]

def configure_ptt_key():
    step_header(5, "Configure PTT Key")

    info("Choose the key that will be simulated when someone presses the")
    info("web PTT button. This must match the PTT key set in vPilot.")
    print()

    # Show quick options
    for i, (key, desc) in enumerate(QUICK_OPTIONS, 1):
        print(f"    {bold(str(i))}. {desc}")
    print(f"    {bold(str(len(QUICK_OPTIONS) + 1))}. {dim('Custom key (type the key name)')}")
    print()

    while True:
        choice = prompt("Pick a number or type a key name", default="1")

        # Check if it's a numbered choice
        try:
            idx = int(choice)
            if 1 <= idx <= len(QUICK_OPTIONS):
                key_name = QUICK_OPTIONS[idx - 1][0]
                success(f"PTT key set to: {bold(key_name)}")
                return key_name
            elif idx == len(QUICK_OPTIONS) + 1:
                # Custom key
                custom = prompt("Enter key name (e.g. f5, scroll_lock, page_up)").lower().strip()
                if custom in SUPPORTED_KEYS:
                    success(f"PTT key set to: {bold(custom)} ({SUPPORTED_KEYS[custom]})")
                    return custom
                # Also accept single characters (pynput supports char keys)
                elif len(custom) == 1 and custom.isalpha():
                    success(f"PTT key set to: {bold(custom)}")
                    return custom
                else:
                    warn(f"'{custom}' is not a recognised key name.")
                    info("Supported special keys:")
                    _print_supported_keys()
                    continue
        except ValueError:
            pass

        # Typed a key name directly
        key_lower = choice.lower().strip()
        if key_lower in SUPPORTED_KEYS:
            success(f"PTT key set to: {bold(key_lower)} ({SUPPORTED_KEYS[key_lower]})")
            return key_lower
        elif len(key_lower) == 1 and key_lower.isalpha():
            success(f"PTT key set to: {bold(key_lower)}")
            return key_lower
        else:
            warn(f"'{choice}' is not a recognised key name or option number.")
            info("Supported special keys:")
            _print_supported_keys()


def _print_supported_keys():
    """Print supported key names in columns."""
    keys = sorted(SUPPORTED_KEYS.keys())
    cols = 4
    rows = (len(keys) + cols - 1) // cols
    for r in range(rows):
        parts = []
        for c in range(cols):
            idx = r + c * rows
            if idx < len(keys):
                parts.append(f"  {dim(keys[idx]):20s}")
        print("  " + "".join(parts))
    print()

# ---------------------------------------------------------------------------
# Step 6 - Configure ports
# ---------------------------------------------------------------------------

def configure_ports():
    step_header(6, "Configure Ports")

    info("The HTTP server serves the web PTT page to browsers.")
    info("The WebSocket server handles real-time PTT communication.")
    print()

    while True:
        http_raw = prompt("HTTP port", default=8080)
        try:
            http_port = int(http_raw)
        except ValueError:
            warn("Please enter a valid number.")
            continue
        if not (1024 <= http_port <= 65535):
            warn("Port must be between 1024 and 65535.")
            continue
        break

    while True:
        ws_raw = prompt("WebSocket port", default=8765)
        try:
            ws_port = int(ws_raw)
        except ValueError:
            warn("Please enter a valid number.")
            continue
        if not (1024 <= ws_port <= 65535):
            warn("Port must be between 1024 and 65535.")
            continue
        if ws_port == http_port:
            warn("WebSocket port must be different from the HTTP port.")
            continue
        break

    # Quick port availability check
    for label, port in [("HTTP", http_port), ("WebSocket", ws_port)]:
        if _port_in_use(port):
            warn(f"{label} port {port} appears to be in use by another program.")
            info("It may work once that program is closed, or choose a different port.")
        else:
            success(f"{label} port {bold(str(port))} is available.")

    return http_port, ws_port


def _port_in_use(port):
    """Check if a TCP port is currently in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Step 7 - Write config.json
# ---------------------------------------------------------------------------

def write_config(ptt_key, http_port, ws_port):
    step_header(7, "Write Configuration")

    config = {
        "ptt_key": ptt_key,
        "http_port": http_port,
        "ws_port": ws_port,
    }

    config_path = os.path.join(BASE_DIR, "config.json")

    if os.path.isfile(config_path):
        info(f"Existing config.json found at {config_path}")
        if not confirm("Overwrite it?", default_yes=True):
            warn("Keeping existing config.json. Your new settings were NOT saved.")
            return config

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")
        success(f"Configuration written to {bold(config_path)}")
    except OSError as exc:
        error(f"Failed to write config.json: {exc}")
        error("Please check file permissions and try again.")
        sys.exit(1)

    return config

# ---------------------------------------------------------------------------
# Step 8 - Summary and next steps
# ---------------------------------------------------------------------------

def print_summary(config):
    step_header(8, "Setup Complete!")

    print()
    print(f"  {bold('Saved configuration:')}")
    print(f"    PTT Key        : {bold_green(config['ptt_key'])}")
    print(f"    HTTP Port      : {bold_green(str(config['http_port']))}")
    print(f"    WebSocket Port : {bold_green(str(config['ws_port']))}")
    print()

    # Determine LAN IP for helpful URLs
    lan_ip = _get_lan_ip()
    http_port = config["http_port"]
    ws_port = config["ws_port"]

    print(f"  {bold('Next steps:')}")
    print()
    print(f"    {bold('1.')} Set your VoIP app (Discord, phone, etc.) audio output")
    print(f"       to {bold_yellow('CABLE Input (VB-Audio Virtual Cable)')}")
    print()
    print(f"    {bold('2.')} In vPilot, set the microphone to")
    print(f"       {bold_yellow('CABLE Output (VB-Audio Virtual Cable)')}")
    print()
    print(f"    {bold('3.')} In vPilot, set the PTT key to {bold_yellow(config['ptt_key'])}")
    print(f"       (must match the key configured above)")
    print()
    print(f"    {bold('4.')} Start the server:")
    print(f"       {dim('Console mode:')}  {bold('python remote_vatsim.py')}")
    print(f"       {dim('GUI mode:')}      {bold('python gui.py')}")
    print()

    print(f"  {bold('URLs (once the server is running):')}")
    print(f"    Local  :  {bold_cyan(f'http://localhost:{http_port}')}")
    if lan_ip:
        print(f"    Network:  {bold_cyan(f'http://{lan_ip}:{http_port}')}")
        print(f"    {dim('(Share the Network URL with the remote person)')}")
    else:
        info("Could not detect LAN IP. Use your machine's IP address + port.")
    print()

    print(f"  {bold_green('Setup complete. Happy flying!')}")
    print()


def _get_lan_ip():
    """Best-effort detection of the machine's LAN IP address."""
    try:
        # Connect to a public IP (no data sent) to find the default route interface
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        cls()
        welcome()
        check_python()
        install_dependencies()
        check_vb_cable()
        ptt_key = configure_ptt_key()
        http_port, ws_port = configure_ports()
        config = write_config(ptt_key, http_port, ws_port)
        print_summary(config)
    except KeyboardInterrupt:
        print()
        print()
        warn("Setup cancelled by user.")
        print()
        sys.exit(130)


if __name__ == "__main__":
    main()
