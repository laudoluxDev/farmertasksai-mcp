#!/usr/bin/env python3
"""
TasksAI MCP GUI Installer — Universal Multi-Vertical

Single .exe — no zip, no terminal, no typing.
User double-clicks → GUI opens → clicks Install → done.

The download URL embeds a one-time token:
  /download/installer/{token}
The installer fetches the real license key from the API using that token,
pre-fills it in the GUI, and the user never sees or types a key.
"""

import json
import os
import platform
import shutil
import sys
import threading
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

# ── Vertical configuration (baked in at build time) ──────────────────────────

# Try build-time config first (baked into binary by PyInstaller), then env vars
try:
    import _build_config as _bc
except ImportError:
    _bc = None

def _cfg(attr, env_key, default):
    """Read from baked config, then env, then default."""
    if _bc and hasattr(_bc, attr):
        return getattr(_bc, attr)
    return os.getenv(env_key, default)

PRODUCT_ID     = _cfg("PRODUCT_ID",     "TASKSAI_PRODUCT_ID",     "farmer")
PRODUCT_NAME   = _cfg("PRODUCT_NAME",   "TASKSAI_PRODUCT_NAME",   "FarmerTasksAI")
MCP_KEY_NAME   = _cfg("MCP_KEY_NAME",   "TASKSAI_MCP_KEY",        "farmertasksai")
ENV_VAR_NAME   = _cfg("ENV_VAR_NAME",   "TASKSAI_ENV_VAR",        "FARMERTASKSAI_LICENSE_KEY")
LICENSE_PREFIX = _cfg("LICENSE_PREFIX", "TASKSAI_LIC_PREFIX",     "ft_")
SUPPORT_EMAIL  = _cfg("SUPPORT_EMAIL", "TASKSAI_SUPPORT_EMAIL",  "support@farmertasksai.com")
DOMAIN         = _cfg("DOMAIN",         "TASKSAI_DOMAIN",         "farmertasksai.com")
APP_FOLDER     = _cfg("APP_FOLDER",     "TASKSAI_APP_FOLDER",     "FarmerTasksAI")
SERVER_BIN     = _cfg("SERVER_BIN",     "TASKSAI_SERVER_BIN",     "farmertasksai-server")
ACCENT_COLOR   = os.getenv("TASKSAI_ACCENT_COLOR",  "#2563eb")
API_BASE       = "https://api.lawtasksai.com"

INSTALLER_VERSION = "3.0.0"


# ── Helpers (reused from install.py) ─────────────────────────────────────────

def is_bundled():
    return getattr(sys, "frozen", False)

def get_install_dir():
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / APP_FOLDER

def get_server_binary_name():
    if platform.system() == "Windows":
        return f"{SERVER_BIN}.exe"
    return SERVER_BIN

def get_bundled_server_path():
    bin_name = get_server_binary_name()
    if is_bundled():
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        for candidate in [meipass / bin_name, Path(sys.executable).parent / bin_name]:
            if candidate.exists():
                return candidate
    else:
        for candidate in [Path(__file__).parent / bin_name, Path(__file__).parent / "dist" / bin_name]:
            if candidate.exists():
                return candidate
    return None

def get_mcp_clients():
    """Detect installed MCP clients. Imported from install.py logic."""
    system = platform.system()
    clients = {}
    if system == "Darwin":
        claude_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        if Path("/Applications/Claude.app").exists() or claude_path.parent.exists():
            clients["Claude Desktop"] = claude_path
        cursor_path = Path.home() / ".cursor" / "mcp.json"
        if (Path("/Applications/Cursor.app").exists() or cursor_path.parent.exists()):
            clients["Cursor"] = cursor_path
        windsurf_path = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        if Path("/Applications/Windsurf.app").exists() or windsurf_path.parent.exists():
            clients["Windsurf"] = windsurf_path
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        localappdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))

        # Claude Desktop — always write to standard path, create dir if needed
        # Standard path: %APPDATA%\Claude\claude_desktop_config.json
        claude_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
        claude_path.parent.mkdir(parents=True, exist_ok=True)
        clients["Claude Desktop"] = claude_path

        # Also check for Claude in LocalAppData (some versions)
        import glob as _glob
        for pattern in [
            str(Path(localappdata) / "AnthropicClaude" / "app-*"),
        ]:
            for match in _glob.glob(pattern):
                alt_path = Path(match) / "claude_desktop_config.json"
                if alt_path.parent.exists() and str(alt_path) != str(claude_path):
                    clients[f"Claude Desktop ({match})"] = alt_path
                break

        # Cursor
        cursor_paths = [
            Path(appdata) / "Cursor" / "User" / "globalStorage" / "cursor-mcp" / "mcp.json",
            Path(appdata) / "Cursor" / "User" / "mcp.json",
        ]
        for cp in cursor_paths:
            if cp.parent.exists():
                clients["Cursor"] = cp
                break

        # Windsurf
        windsurf_paths = [
            Path(localappdata) / "Windsurf" / "User" / "globalStorage" / "windsurf-mcp" / "mcp_config.json",
            Path(appdata) / "Windsurf" / "User" / "globalStorage" / "windsurf-mcp" / "mcp_config.json",
        ]
        for wp in windsurf_paths:
            if wp.parent.exists():
                clients["Windsurf"] = wp
                break

    return clients

def _get_mcp_entry(server_path, license_key):
    path_str = str(server_path)
    if path_str.endswith(".py"):
        return {"command": sys.executable, "args": [path_str], "env": {ENV_VAR_NAME: license_key}}
    return {"command": path_str, "env": {ENV_VAR_NAME: license_key, "TASKSAI_LICENSE_KEY": license_key}}

def update_config(config_path, server_path, license_key):
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {}
    if config_path.exists():
        backup = config_path.with_suffix(f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json")
        shutil.copy2(config_path, backup)
        try:
            with open(config_path) as f:
                config = json.load(f)
        except Exception:
            config = {}
    config.setdefault("mcpServers", {})[MCP_KEY_NAME] = _get_mcp_entry(server_path, license_key)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

def resolve_license_from_token(token: str) -> str | None:
    """Decode a base64 key token returned from the download endpoint."""
    try:
        import base64 as _b64
        # Try as base64 first (from X-License-Token header embedded in filename)
        padded = token + "==" [:(4 - len(token) % 4) % 4]
        key = _b64.urlsafe_b64decode(padded).decode()
        if key.startswith(("lt_", "rt_", "ft_", "tt_", "th_", "mt_", "ct_")):
            return key
    except Exception:
        pass
    # Fallback: call API
    try:
        req = urllib.request.Request(
            f"{API_BASE}/v1/installer-key?k={token}",
            headers={"User-Agent": f"{PRODUCT_NAME}-Installer/{INSTALLER_VERSION}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("license_key")
    except Exception:
        return None

def verify_license(license_key: str) -> tuple[bool, int, str]:
    """Returns (valid, credits, message)."""
    try:
        req = urllib.request.Request(
            f"{API_BASE}/v1/credits/balance",
            headers={"Authorization": f"Bearer {license_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            credits = data.get("credits_balance", 0)
            return True, credits, f"{credits} credits available"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, 0, "Invalid license key"
        return False, 0, f"Server error ({e.code})"
    except Exception as e:
        return False, 0, f"Could not reach server ({type(e).__name__})"


# ── GUI ───────────────────────────────────────────────────────────────────────

def run_gui(prefilled_key: str = "", prefilled_token: str = ""):
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        # Fallback to terminal if tkinter not available
        run_terminal(prefilled_key)
        return

    # ── Window setup ──────────────────────────────────────────────────────────
    root = tk.Tk()
    root.title(f"{PRODUCT_NAME} Installer")
    root.resizable(False, False)

    W, H = 560, 600
    root.configure(bg="#f9fafb")

    # Center on screen
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    # Never taller than 90% of screen
    H = min(H, int(sh * 0.90))
    x = (sw - W) // 2
    y = (sh - H) // 2
    root.geometry(f"{W}x{H}+{x}+{y}")
    root.minsize(W, 500)

    # ── State ─────────────────────────────────────────────────────────────────
    license_var   = tk.StringVar(value=prefilled_key)
    status_var    = tk.StringVar(value="")
    progress_var  = tk.DoubleVar(value=0)
    install_done  = tk.BooleanVar(value=False)
    log_lines     = []

    # ── Header ────────────────────────────────────────────────────────────────
    header = tk.Frame(root, bg=ACCENT_COLOR, height=72)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(header, text=f"  {PRODUCT_NAME} Installer",
             font=("Helvetica", 18, "bold"), fg="white", bg=ACCENT_COLOR,
             anchor="w").pack(fill="both", expand=True, padx=20)

    # ── Body ──────────────────────────────────────────────────────────────────
    body = tk.Frame(root, bg="#f9fafb", padx=28, pady=20)
    body.pack(fill="both", expand=True)

    # License key field
    tk.Label(body, text="License Key", font=("Helvetica", 11, "bold"),
             bg="#f9fafb", fg="#374151", anchor="w").pack(fill="x")

    key_frame = tk.Frame(body, bg="#f9fafb")
    key_frame.pack(fill="x", pady=(4, 0))

    key_entry = tk.Entry(key_frame, textvariable=license_var, font=("Courier", 11),
                         fg="#1f2937", bg="white", relief="solid", bd=1,
                         highlightthickness=2, highlightcolor=ACCENT_COLOR,
                         highlightbackground="#d1d5db", width=34)
    key_entry.pack(side="left", fill="x", expand=True, ipady=7)

    def verify_clicked():
        key = license_var.get().strip()
        if not key:
            status_var.set("⚠️  Please enter your license key")
            return
        status_var.set("Verifying...")
        verify_btn.config(state="disabled")
        def do_verify():
            valid, credits, msg = verify_license(key)
            if valid:
                status_var.set(f"✅  Valid — {credits} credits ready")
                install_btn.config(state="normal")
            else:
                status_var.set(f"❌  {msg}")
            verify_btn.config(state="normal")
        threading.Thread(target=do_verify, daemon=True).start()

    verify_btn = tk.Button(key_frame, text="Verify", command=verify_clicked,
                           font=("Helvetica", 10), bg=ACCENT_COLOR, fg="white",
                           relief="flat", padx=14, cursor="hand2",
                           activebackground="#1d4ed8", activeforeground="white")
    verify_btn.pack(side="left", padx=(8, 0), ipady=7)

    status_lbl = tk.Label(body, textvariable=status_var, font=("Helvetica", 10),
                          bg="#f9fafb", fg="#6b7280", anchor="w")
    status_lbl.pack(fill="x", pady=(6, 0))

    # Detected clients
    tk.Frame(body, bg="#e5e7eb", height=1).pack(fill="x", pady=14)
    clients = get_mcp_clients()
    tk.Label(body, text="Detected AI tools:", font=("Helvetica", 10, "bold"),
             bg="#f9fafb", fg="#374151", anchor="w").pack(fill="x")

    if clients:
        for name in clients:
            row = tk.Frame(body, bg="#f9fafb")
            row.pack(fill="x", pady=1)
            tk.Label(row, text="  ✓ " + name, font=("Helvetica", 10),
                     bg="#f9fafb", fg="#059669", anchor="w").pack(side="left")
    else:
        tk.Label(body, text="  ⚠️  No supported AI tools found (Claude Desktop, Cursor, Windsurf)",
                 font=("Helvetica", 10), bg="#f9fafb", fg="#d97706", anchor="w",
                 wraplength=440, justify="left").pack(fill="x")

    tk.Frame(body, bg="#e5e7eb", height=1).pack(fill="x", pady=14)

    # Progress log — scrollable
    log_frame = tk.Frame(body, bg="#1f2937")
    log_frame.pack(fill="both", expand=True)
    log_scroll = tk.Scrollbar(log_frame)
    log_scroll.pack(side="right", fill="y")
    log_text = tk.Text(log_frame, height=8, font=("Courier", 9), bg="#1f2937", fg="#d1fae5",
                       relief="flat", state="disabled", wrap="word",
                       yscrollcommand=log_scroll.set)
    log_text.pack(side="left", fill="both", expand=True)
    log_scroll.config(command=log_text.yview)

    def log(msg):
        log_lines.append(msg)
        log_text.config(state="normal")
        log_text.insert("end", msg + "\n")
        log_text.see("end")
        log_text.config(state="disabled")
        root.update_idletasks()

    # Progress bar
    prog = ttk.Progressbar(body, variable=progress_var, maximum=100, length=460)
    prog.pack(fill="x", pady=(8, 0))

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_frame = tk.Frame(root, bg="#f3f4f6", pady=12)
    btn_frame.pack(fill="x", side="bottom")

    def close_clicked():
        root.destroy()

    close_btn = tk.Button(btn_frame, text="Close", command=close_clicked,
                          font=("Helvetica", 10), bg="#e5e7eb", fg="#374151",
                          relief="flat", padx=20, cursor="hand2")
    close_btn.pack(side="right", padx=(0, 16))

    def do_install():
        install_btn.config(state="disabled")
        key = license_var.get().strip()
        if not key:
            status_var.set("⚠️  Enter your license key first")
            install_btn.config(state="normal")
            return

        def run():
            try:
                progress_var.set(10)
                log(f"Starting {PRODUCT_NAME} installation...")

                # Install server binary
                install_dir = get_install_dir()
                log(f"   Install dir: {install_dir}")
                install_dir.mkdir(parents=True, exist_ok=True)
                progress_var.set(25)

                bundled = get_bundled_server_path()
                server_dest = install_dir / get_server_binary_name()
                log(f"   Bundled server: {bundled}")
                log(f"   Server dest: {server_dest}")

                if bundled:
                    # If target exists and is locked (e.g. Claude Desktop running), try removing first
                    if server_dest.exists():
                        try:
                            server_dest.unlink()
                        except PermissionError:
                            log("⚠️  Server binary is locked — close Claude Desktop and retry")
                            status_var.set("⚠️  Close Claude Desktop first, then click Install again")
                            install_btn.config(state="normal")
                            return
                    shutil.copy2(str(bundled), str(server_dest))
                    if platform.system() != "Windows":
                        server_dest.chmod(0o755)
                    log(f"✓ Server installed to {server_dest}")
                else:
                    log("⚠️  Server binary not found in bundle")
                    log("   This installer may not have the server bundled.")
                    log("   The server may already be installed from a previous run.")

                progress_var.set(45)

                # Save .env
                env_path = install_dir / ".env"
                with open(env_path, "w") as f:
                    f.write(f"{ENV_VAR_NAME}={key}\nTASKSAI_LICENSE_KEY={key}\n")
                log("✓ License key saved")
                progress_var.set(60)

                # Configure MCP clients
                if clients:
                    for name, config_path in clients.items():
                        try:
                            update_config(config_path, server_dest, key)
                            log(f"✓ Configured {name}")
                            log(f"   Config: {config_path}")
                        except Exception as e:
                            log(f"⚠️  {name}: {e}")
                else:
                    log("⚠️  No AI tools configured")
                    log(f"   Install Claude Desktop: https://claude.ai/download")

                progress_var.set(85)

                # Verify
                valid, credits, msg = verify_license(key)
                if valid:
                    log(f"✓ License verified — {credits} credits ready")
                else:
                    log(f"⚠️  {msg}")

                progress_var.set(100)
                status_var.set("✅  Installation complete! Restart your AI tool.")
                install_done.set(True)
                close_btn.config(text="Done ✓", bg=ACCENT_COLOR, fg="white")
                log(f"\nYou can now delete this installer.")
                log(f"Restart Claude Desktop (or your AI tool) to begin.")

            except Exception as e:
                import traceback
                log(f"❌ Error: {e}")
                log(f"   Details: {traceback.format_exc()}")
                status_var.set(f"❌  Installation failed: {e}")
                install_btn.config(state="normal")

        threading.Thread(target=run, daemon=True).start()

    install_btn = tk.Button(btn_frame, text=f"Install {PRODUCT_NAME}  →",
                            command=do_install, font=("Helvetica", 11, "bold"),
                            bg=ACCENT_COLOR, fg="white", relief="flat",
                            padx=24, cursor="hand2",
                            activebackground="#1d4ed8", activeforeground="white",
                            state="disabled" if not prefilled_key else "normal")
    install_btn.pack(side="right", padx=(0, 8))

    tk.Label(btn_frame, text=f"v{INSTALLER_VERSION}", font=("Helvetica", 9),
             bg="#f3f4f6", fg="#9ca3af").pack(side="left", padx=16)

    # ── Auto-resolve token if provided ───────────────────────────────────────
    if prefilled_token and not prefilled_key:
        status_var.set("Loading your license key...")
        def resolve_token():
            key = resolve_license_from_token(prefilled_token)
            if key:
                license_var.set(key)
                status_var.set("✅  License key loaded — click Install to continue")
                install_btn.config(state="normal")
                key_entry.config(fg="#059669")
            else:
                status_var.set("⚠️  Could not auto-load key — enter it manually below")
        threading.Thread(target=resolve_token, daemon=True).start()
    elif prefilled_key:
        # Key already known — auto-verify in background
        status_var.set("Verifying your license...")
        def auto_verify():
            valid, credits, msg = verify_license(prefilled_key)
            if valid:
                status_var.set(f"✅  {credits} credits ready — click Install to continue")
                install_btn.config(state="normal")
                key_entry.config(fg="#059669")
            else:
                status_var.set(f"⚠️  {msg}")
                install_btn.config(state="normal")  # let them try anyway
        threading.Thread(target=auto_verify, daemon=True).start()

    root.mainloop()


def run_terminal(prefilled_key: str = ""):
    """Fallback terminal mode (no tkinter)."""
    import install
    install.main()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    # Check for token or key passed as CLI arg (from download URL redirect)
    token = ""
    key = os.getenv("TASKSAI_BAKED_LICENSE_KEY", "").strip()

    # Check .env next to the exe
    if not key:
        if is_bundled():
            installer_dir = Path(sys.executable).parent
        else:
            installer_dir = Path(__file__).parent
        env_path = installer_dir / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text().splitlines():
                    for var in (ENV_VAR_NAME, "TASKSAI_LICENSE_KEY"):
                        if line.startswith(f"{var}="):
                            candidate = line.split("=", 1)[1].strip()
                            if candidate and candidate != "YOUR_KEY_HERE":
                                key = candidate
                                break
            except Exception:
                pass

    # Check args for --token or --key
    for arg in sys.argv[1:]:
        if arg.startswith("--token="):
            token = arg.split("=", 1)[1]
        elif arg.startswith("--key="):
            key = arg.split("=", 1)[1]

    run_gui(prefilled_key=key, prefilled_token=token)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Last-resort crash log — write to file next to exe
        import traceback
        crash_path = Path(sys.executable).parent / "install-crash.log" if getattr(sys, 'frozen', False) else Path("install-crash.log")
        try:
            with open(crash_path, "w") as f:
                f.write(f"Crash at {datetime.now()}\n\n")
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
