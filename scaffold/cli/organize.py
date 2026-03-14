import os
import socket
import subprocess
import sys
import threading
import time

from scaffold.config import load_config


def _port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def cmd_organize(port: int = 7890, no_open: bool = False) -> None:
    url = f"http://localhost:{port}/organize"

    # If the server is already running, just (re-)open the browser.
    if _port_in_use(port):
        print(f"Organizer already running  →  {url}")
        if not no_open:
            subprocess.run(["open", url], check=False)
        return

    # Initialize AppKit on the main thread before any NSWorkspace calls.
    # Without this, NSWorkspace.runningApplications() may return empty.
    try:
        from AppKit import NSApplication
        NSApplication.sharedApplication()
    except Exception:
        pass

    # Trigger the macOS Accessibility permission prompt from the main thread.
    # AXIsProcessTrustedWithOptions must be called from the main thread so that
    # macOS correctly identifies and highlights this process in System Settings.
    import ApplicationServices as AS
    trusted = AS.AXIsProcessTrustedWithOptions(None)
    if not trusted:
        print(f"\nScaffold needs Accessibility permission.")
        print(f"Python: {sys.executable}")
        print(f"\nOpening System Settings → Accessibility now...")
        AS.AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
        print("Enable the toggle for this process, then run 'scaffold organize' again.\n")
        # Don't exit — the server still starts so the user can come back to it,
        # but warn them that windows won't load until permission is granted.

    import scaffold.server as srv
    srv._config = load_config()

    if not no_open:
        threading.Timer(0.5, lambda: subprocess.run(["open", url], check=False)).start()

    print(f"Scaffold Organizer  →  {url}")
    print("Press Ctrl+C to quit.")

    try:
        srv.run_server(port)   # blocks on main thread
    except KeyboardInterrupt:
        print("\nDone.")
