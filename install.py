#!/usr/bin/env python3
"""
TasksAI MCP Installer — Universal Multi-Vertical

Installs the TasksAI MCP server for all supported MCP clients:
  - Claude Desktop
  - Claude Code (CLI)
  - Cursor
  - Windsurf
  - Cline (VS Code extension)

This installer:
  1. Copies the MCP server binary to a permanent OS location
  2. Saves your license key there
  3. Configures all detected MCP clients to use it
  4. Verifies your license is valid

After installation, you can delete this installer.
The server binary in the permanent location does the actual work.

Usage (Python / development mode):
    python3 install.py

In production, users run the .exe / binary directly — no Python needed.
"""

import json
import os
import platform
import shutil
import sys
from pathlib import Path
from datetime import datetime

# ── Vertical configuration ─────────────────────────────────────────────────────
# These values are baked in at build time for each vertical's installer.
# In dev/source mode, defaults to FarmerTasksAI.

PRODUCT_ID     = os.getenv("TASKSAI_PRODUCT_ID",   "farmer")
PRODUCT_NAME   = os.getenv("TASKSAI_PRODUCT_NAME",  "FarmerTasksAI")

# Derive defaults from PRODUCT_NAME if not explicitly overridden.
# e.g. "FarmerTasksAI" -> mcp key "farmertasksai", folder "FarmerTasksAI", env var "FARMERTASKSAI_LICENSE_KEY"
_product_slug  = PRODUCT_NAME.lower().replace(" ", "")   # e.g. "farmertasksai"
MCP_KEY_NAME   = os.getenv("TASKSAI_MCP_KEY",       _product_slug)    # key in MCP JSON configs
ENV_VAR_NAME   = os.getenv("TASKSAI_ENV_VAR",       f"{_product_slug.upper()}_LICENSE_KEY")
LICENSE_PREFIX = os.getenv("TASKSAI_LIC_PREFIX",    "ft_")            # e.g. "rt_" for realtor
SUPPORT_EMAIL  = os.getenv("TASKSAI_SUPPORT_EMAIL", f"support@{os.getenv('TASKSAI_DOMAIN', 'farmertasksai.com')}")
DOMAIN         = os.getenv("TASKSAI_DOMAIN",        "farmertasksai.com")
APP_FOLDER     = os.getenv("TASKSAI_APP_FOLDER",    PRODUCT_NAME)     # OS install dir name
SERVER_BIN     = os.getenv("TASKSAI_SERVER_BIN",    f"{_product_slug}-server")  # binary name (no ext)

INSTALLER_VERSION = "2.0.0"

# ── Helpers ────────────────────────────────────────────────────────────────────

def is_bundled() -> bool:
    """True when running as a PyInstaller .exe / binary."""
    return getattr(sys, "frozen", False)


def is_interactive_terminal() -> bool:
    """True if stdin is a real terminal (not a double-clicked file)."""
    return sys.stdin.isatty()


def pause_if_finder():
    """
    Keep the window open when double-clicked from Finder / File Explorer,
    so the user can read the output before the window closes.
    """
    if not is_interactive_terminal():
        input("\n  Press Enter to close this window... ")


# ── Install directory ──────────────────────────────────────────────────────────

def get_install_dir() -> Path:
    """
    Return the permanent OS-specific install directory for this vertical.

    Windows : %LOCALAPPDATA%\\{APP_FOLDER}\\
    Mac     : ~/Library/Application Support/{APP_FOLDER}/
    Linux   : ~/.local/share/{APP_FOLDER}/
    """
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / APP_FOLDER


def get_server_binary_name() -> str:
    """Return the platform-correct server binary filename."""
    if platform.system() == "Windows":
        return f"{SERVER_BIN}.exe"
    return SERVER_BIN


def get_server_install_path() -> Path:
    """Full path to the server binary in the install directory."""
    return get_install_dir() / get_server_binary_name()


def get_env_install_path() -> Path:
    """Full path to the .env file in the install directory."""
    return get_install_dir() / ".env"


# ── Bundled server binary ──────────────────────────────────────────────────────

def get_bundled_server_path() -> Path | None:
    """
    When running as a PyInstaller bundle, the server binary is extracted
    to sys._MEIPASS (the temp unpack dir). Return its path, or None if not found.
    In dev/source mode, look for the binary next to this script.
    """
    bin_name = get_server_binary_name()

    if is_bundled():
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        candidate = meipass / bin_name
        if candidate.exists():
            return candidate
        # Fallback: look in same dir as the installer executable
        candidate = Path(sys.executable).parent / bin_name
        if candidate.exists():
            return candidate
    else:
        # Dev mode: look next to install.py, or in dist/
        for candidate in [
            Path(__file__).parent / bin_name,
            Path(__file__).parent / "dist" / bin_name,
        ]:
            if candidate.exists():
                return candidate

    return None


def install_server_binary(install_dir: Path) -> Path:
    """
    Copy the server binary from the bundle / source tree to the install dir.
    Returns the final installed path.
    Raises RuntimeError if the binary can't be found.
    """
    install_dir.mkdir(parents=True, exist_ok=True)
    dest = install_dir / get_server_binary_name()

    bundled = get_bundled_server_path()
    if bundled:
        shutil.copy2(str(bundled), str(dest))
        # Ensure executable on Unix
        if platform.system() != "Windows":
            dest.chmod(0o755)
        return dest

    # Dev/source mode fallback: we ARE server.py, use Python to run it
    # (This path is only hit when building/testing without PyInstaller)
    server_py = Path(__file__).parent / "server.py"
    if server_py.exists():
        dest_py = install_dir / "server.py"
        shutil.copy2(str(server_py), str(dest_py))
        return dest_py

    raise RuntimeError(
        f"Could not find server binary '{get_server_binary_name()}'. "
        "Please re-download the installer from the website."
    )


# ── License key ────────────────────────────────────────────────────────────────

def get_license_key(install_dir: Path) -> str:
    """
    Read license key from the install dir .env (upgrade/reinstall path),
    then from the installer's own directory, then prompt the user.
    """
    # 0. Key baked into the binary at build time (most reliable — works even if .env is missing)
    baked_key = os.getenv("TASKSAI_BAKED_LICENSE_KEY", "").strip()
    if baked_key and baked_key not in ("YOUR_KEY_HERE", ""):
        print(f"  License key loaded automatically.")
        return baked_key

    # 1. Already installed — use existing key
    env_path = install_dir / ".env"
    if env_path.exists():
        key = _read_key_from_env(env_path)
        if key:
            print(f"  Found existing license key in install directory.")
            return key

    # 2. .env next to installer (downloaded zip workflow)
    # When bundled by PyInstaller, __file__ points to _MEIPASS (temp dir).
    # The .env ships next to the .exe itself, so use sys.executable's dir.
    if is_bundled():
        installer_dir = Path(sys.executable).parent
    else:
        installer_dir = Path(__file__).parent

    for env_candidate in [
        installer_dir / ".env",          # next to the .exe (primary)
        installer_dir / ".. " / ".env",  # one level up (just in case)
        Path(__file__).parent / ".env",  # _MEIPASS (bundled helper files)
    ]:
        if env_candidate.exists():
            key = _read_key_from_env(env_candidate)
            if key:
                print(f"  Found license key in {env_candidate.resolve()}")
                return key

    # 3. Prompt
    print(f"\n  Enter your {PRODUCT_NAME} license key (starts with {LICENSE_PREFIX}):")
    key = input("   > ").strip()
    if not key:
        print(f"  No license key provided.")
        print(f"  Check your purchase confirmation email from {SUPPORT_EMAIL}")
        sys.exit(1)
    if not key.startswith(LICENSE_PREFIX):
        print(f"  ⚠️  That doesn't look like a {PRODUCT_NAME} key (expected prefix: {LICENSE_PREFIX}).")
        print(f"     Check your purchase confirmation email or contact {SUPPORT_EMAIL}")
        # Don't exit — let verification catch it
    return key


def _read_key_from_env(env_path: Path) -> str | None:
    """Extract the license key from a .env file. Returns None if not found."""
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            for var in (ENV_VAR_NAME, "TASKSAI_LICENSE_KEY", "LAWTASKSAI_LICENSE_KEY"):
                if line.startswith(f"{var}="):
                    key = line.split("=", 1)[1].strip()
                    if key and key not in ("YOUR_KEY_HERE", ""):
                        return key
    return None


def save_license_key(install_dir: Path, license_key: str):
    """Write the license key to .env in the permanent install directory."""
    install_dir.mkdir(parents=True, exist_ok=True)
    env_path = install_dir / ".env"
    # Preserve any existing entries, just update/add the key
    lines = []
    key_written = False
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if line.startswith(f"{ENV_VAR_NAME}=") or line.startswith("TASKSAI_LICENSE_KEY="):
                    lines.append(f"{ENV_VAR_NAME}={license_key}\n")
                    key_written = True
                else:
                    lines.append(line)
    if not key_written:
        lines.append(f"{ENV_VAR_NAME}={license_key}\n")
        lines.append(f"TASKSAI_LICENSE_KEY={license_key}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)


# ── MCP client detection ───────────────────────────────────────────────────────

def _resolve_client_path(candidates: list[Path]) -> Path:
    """
    Return the first candidate whose parent directory exists,
    or the first candidate as default (installer will create it).
    """
    for path in candidates:
        if path.parent.exists():
            return path
    return candidates[0]


def get_mcp_clients() -> dict[str, Path]:
    """
    Detect installed MCP clients and return {client_name: config_path}.
    Checks Claude Desktop, Claude Code, Cursor, Windsurf, and Cline (VS Code).
    """
    system = platform.system()
    clients = {}

    if system == "Darwin":
        # Claude Desktop
        claude_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        if (Path.home() / "Applications" / "Claude.app").exists() or \
           Path("/Applications/Claude.app").exists() or \
           claude_path.parent.exists():
            clients["Claude Desktop"] = claude_path

        # Claude Code CLI (~/.claude.json)
        claude_code_path = Path.home() / ".claude.json"
        if claude_code_path.exists() or (Path.home() / ".claude").is_dir():
            clients["Claude Code"] = claude_code_path

        # Cursor
        cursor_native = Path.home() / ".cursor" / "mcp.json"
        cursor_cline  = Path.home() / "Library" / "Application Support" / "Cursor" / "User" / \
                        "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if (Path.home() / "Applications" / "Cursor.app").exists() or \
           Path("/Applications/Cursor.app").exists() or \
           cursor_native.parent.exists() or cursor_cline.parent.exists():
            clients["Cursor"] = _resolve_client_path([cursor_native, cursor_cline])

        # Windsurf
        windsurf_native = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        windsurf_cline  = Path.home() / "Library" / "Application Support" / "Windsurf" / "User" / \
                          "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if (Path.home() / "Applications" / "Windsurf.app").exists() or \
           Path("/Applications/Windsurf.app").exists() or \
           windsurf_native.parent.exists() or windsurf_cline.parent.exists():
            clients["Windsurf"] = _resolve_client_path([windsurf_native, windsurf_cline])

        # Cline standalone (VS Code)
        cline_vscode = Path.home() / "Library" / "Application Support" / "Code" / "User" / \
                       "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if cline_vscode.parent.exists() and "Cursor" not in clients and "Windsurf" not in clients:
            clients["Cline (VS Code)"] = cline_vscode

    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        local   = os.environ.get("LOCALAPPDATA", "")

        # Claude Desktop
        claude_path = Path(appdata) / "Claude" / "claude_desktop_config.json"
        if claude_path.parent.exists():
            clients["Claude Desktop"] = claude_path

        # Claude Code CLI
        claude_code_path = Path.home() / ".claude.json"
        if claude_code_path.exists() or (Path.home() / ".claude").is_dir():
            clients["Claude Code"] = claude_code_path

        # Cursor
        cursor_native = Path(appdata) / "Cursor" / "User" / "globalStorage" / "cursor-mcp" / "mcp.json"
        cursor_cline  = Path(appdata) / "Cursor" / "User" / "globalStorage" / \
                        "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if cursor_native.parent.exists() or cursor_cline.parent.exists():
            clients["Cursor"] = _resolve_client_path([cursor_native, cursor_cline])

        # Windsurf
        windsurf_native = Path(local) / "Windsurf" / "User" / "globalStorage" / \
                          "windsurf-mcp" / "mcp_config.json"
        windsurf_cline  = Path(local) / "Windsurf" / "User" / "globalStorage" / \
                          "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if windsurf_native.parent.exists() or windsurf_cline.parent.exists():
            clients["Windsurf"] = _resolve_client_path([windsurf_native, windsurf_cline])

        # Cline standalone (VS Code)
        cline_vscode = Path(appdata) / "Code" / "User" / "globalStorage" / \
                       "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if cline_vscode.parent.exists() and "Cursor" not in clients and "Windsurf" not in clients:
            clients["Cline (VS Code)"] = cline_vscode

    else:  # Linux
        # Claude Desktop
        claude_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
        if claude_path.parent.exists():
            clients["Claude Desktop"] = claude_path

        # Claude Code CLI
        claude_code_path = Path.home() / ".claude.json"
        if claude_code_path.exists() or (Path.home() / ".claude").is_dir():
            clients["Claude Code"] = claude_code_path

        # Cursor
        cursor_native = Path.home() / ".cursor" / "mcp.json"
        cursor_cline  = Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / \
                        "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if cursor_native.parent.exists() or cursor_cline.parent.exists():
            clients["Cursor"] = _resolve_client_path([cursor_native, cursor_cline])

        # Windsurf
        windsurf_native = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        windsurf_cline  = Path.home() / ".config" / "Windsurf" / "User" / "globalStorage" / \
                          "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if windsurf_native.parent.exists() or windsurf_cline.parent.exists():
            clients["Windsurf"] = _resolve_client_path([windsurf_native, windsurf_cline])

        # Cline standalone (VS Code)
        cline_vscode = Path.home() / ".config" / "Code" / "User" / "globalStorage" / \
                       "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
        if cline_vscode.parent.exists() and "Cursor" not in clients and "Windsurf" not in clients:
            clients["Cline (VS Code)"] = cline_vscode

    return clients


# ── MCP config writing ─────────────────────────────────────────────────────────

def _get_mcp_entry(server_path: Path, license_key: str) -> dict:
    """
    Build the MCP server config entry.

    For a compiled binary (.exe or standalone binary): no Python needed.
    For a .py file (dev/source mode): use python3 as the command.
    """
    path_str = str(server_path)

    if path_str.endswith(".py"):
        # Dev/source mode — need Python
        python = sys.executable
        return {
            "command": python,
            "args": [path_str],
            "env": {
                ENV_VAR_NAME: license_key,
                "TASKSAI_LICENSE_KEY": license_key,
                "TASKSAI_PRODUCT_ID": PRODUCT_ID,
            }
        }
    else:
        # Compiled binary — no Python needed
        return {
            "command": path_str,
            "env": {
                ENV_VAR_NAME: license_key,
                "TASKSAI_LICENSE_KEY": license_key,
                "TASKSAI_PRODUCT_ID": PRODUCT_ID,
            }
        }


def update_config(client_name: str, config_path: Path, server_path: Path, license_key: str):
    """Write the MCP server entry into a client's config file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = {}

    if config_path.exists():
        backup_path = config_path.with_suffix(
            f".backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        )
        shutil.copy2(config_path, backup_path)
        print(f"    💾 Backed up existing config to: {backup_path.name}")
        with open(config_path) as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                print("    ⚠️  Existing config was invalid — starting fresh (backup saved).")
                config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][MCP_KEY_NAME] = _get_mcp_entry(server_path, license_key)

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"    ✅ Config updated: {config_path}")


# ── Post-install verification ──────────────────────────────────────────────────

def verify_installation(license_key: str) -> bool:
    """
    Make a live API call to confirm the license is valid and credits are accessible.
    Uses only stdlib (no httpx) so it works in the bundled .exe without extras.
    """
    import urllib.request
    import urllib.error

    API_BASE = "https://api.lawtasksai.com"
    print()
    print("  Verifying license...")

    try:
        req = urllib.request.Request(
            f"{API_BASE}/v1/credits/balance",
            headers={"Authorization": f"Bearer {license_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json as _json
            data = _json.loads(resp.read())
            credits = data.get("credits_balance", "?")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("  ❌ License key is invalid or expired.")
            print(f"     Check your purchase email or visit {DOMAIN}/account")
        elif e.code == 402:
            print("  ⚠️  License key valid but no credits remaining.")
            print(f"     Purchase more at: https://{DOMAIN}/#pricing")
        else:
            print(f"  ⚠️  Could not verify license (HTTP {e.code}).")
            print("     Installation may still work — restart your MCP client and try.")
        return False
    except Exception as e:
        print(f"  ⚠️  Could not reach {PRODUCT_NAME} servers ({type(e).__name__}).")
        print("     Check your internet connection. Installation files are in place.")
        return False

    try:
        req = urllib.request.Request(
            f"{API_BASE}/v1/skills",
            headers={"Authorization": f"Bearer {license_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            import json as _json
            skills = _json.loads(resp.read())
            skill_count = len(skills) if isinstance(skills, list) else "?"
    except Exception:
        skill_count = "?"

    print(f"  ✅ License verified — {credits} credits available, {skill_count} skills ready")
    return True


# ── No-client fallback ─────────────────────────────────────────────────────────

def no_client_found():
    print()
    print("  No supported MCP clients detected on this machine.")
    print("  Supported: Claude Desktop, Claude Code, Cursor, Windsurf, Cline (VS Code)")
    print()
    print("  ─────────────────────────────────────────────────")
    print("  If you have Claude Desktop installed, open it once so its")
    print("  config folder is created, then run this installer again.")
    print()
    print("  Don't have a supported MCP client yet?")
    print("  → Download Claude Desktop (free): https://claude.ai/download")
    print(f"  → Or contact support: {SUPPORT_EMAIL}")
    print("  ─────────────────────────────────────────────────")
    print()
    pause_if_finder()


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print()
    print("  " + "=" * 54)
    print(f"  {PRODUCT_NAME} MCP Installer  v{INSTALLER_VERSION}")
    print("  " + "=" * 54)
    print()

    # Detect MCP clients
    clients = get_mcp_clients()
    if not clients:
        no_client_found()
        sys.exit(0)

    print(f"  Detected MCP client(s): {', '.join(clients.keys())}")
    print()

    install_dir = get_install_dir()
    print(f"  Install location: {install_dir}")
    print()
    print("  This installer will:")
    print(f"    1. Copy the {PRODUCT_NAME} MCP server to the install location")
    print("    2. Save your license key there")
    print("    3. Configure each detected MCP client")
    print("       (existing configs are backed up first)")
    print()

    # Get license key
    license_key = get_license_key(install_dir)

    # Install server binary to permanent location
    print(f"  Installing {PRODUCT_NAME} server...")
    try:
        server_path = install_server_binary(install_dir)
        print(f"  ✅ Server installed: {server_path}")
    except RuntimeError as e:
        print(f"  ❌ Could not install server: {e}")
        pause_if_finder()
        sys.exit(1)

    # Save license key to install dir
    save_license_key(install_dir, license_key)
    print(f"  ✅ License key saved.")

    # Configure all detected MCP clients
    print()
    configured = []
    for client_name, config_path in clients.items():
        print(f"  Configuring {client_name}...")
        try:
            update_config(client_name, config_path, server_path, license_key)
            configured.append(client_name)
        except Exception as e:
            print(f"    ⚠️  Could not configure {client_name}: {e}")

    # Verify license
    verified = False
    if configured:
        verified = verify_installation(license_key)

    # Done
    print()
    print("  " + "=" * 54)
    print("  ✅ Installation complete!")
    print("  " + "=" * 54)
    print()

    if configured:
        print(f"  Configured: {', '.join(configured)}")
        print()
        if verified:
            print("  Next steps:")
            print("    1. Restart your MCP client(s)")
            print(f"    2. Start using {PRODUCT_NAME} skills!")
            print()
            print("  Try asking Claude:")
            if PRODUCT_ID == "law":
                print('    "Search for a motion to compel skill"')
                print('    "What statute of limitations skills do you have?"')
            elif PRODUCT_ID == "realtor":
                print('    "Search for a CMA report skill"')
                print('    "What listing skills do you have?"')
            elif PRODUCT_ID == "farmer":
                print('    "Search for a USDA application skill"')
                print('    "What crop planning skills do you have?"')
            else:
                print(f'    "Search for a {PRODUCT_NAME} skill for [your task]"')
                print(f'    "What categories of {PRODUCT_NAME} skills are available?"')
        else:
            print("  ⚠️  Verification did not complete — see message above.")
            print("     Your config files are in place.")
            print("     Once resolved, restart your MCP client and try again.")

    print()
    print(f"  ℹ️  You can now delete this installer — it has done its job.")
    print(f"     The server is permanently installed at: {install_dir}")
    print()
    print(f"  Support: {SUPPORT_EMAIL}")
    print(f"  Website: https://{DOMAIN}")
    print()
    pause_if_finder()


if __name__ == "__main__":
    main()
