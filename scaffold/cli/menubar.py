"""
Menu bar launcher for Scaffold.

Creates a persistent macOS status bar item. Clicking "Open Organizer" starts
the Flask server (in a background thread) and opens the browser. "Open at Login"
installs/removes a LaunchAgent so Scaffold starts automatically at login.
"""

import socket
import subprocess
import sys
import threading
from pathlib import Path

LAUNCH_AGENT_LABEL = "com.scaffold.menubar"
LAUNCH_AGENT_PATH  = Path.home() / "Library/LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


# ── Login item helpers ─────────────────────────────────────────────────────

def _login_item_enabled() -> bool:
    return LAUNCH_AGENT_PATH.exists()


def _set_login_item(enabled: bool, port: int) -> None:
    if enabled:
        LAUNCH_AGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{LAUNCH_AGENT_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{sys.executable}</string>
    <string>-m</string>
    <string>scaffold</string>
    <string>menubar</string>
    <string>--port</string>
    <string>{port}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>{Path.home()}/.scaffold/menubar.log</string>
  <key>StandardErrorPath</key>
  <string>{Path.home()}/.scaffold/menubar.log</string>
</dict>
</plist>
"""
        LAUNCH_AGENT_PATH.write_text(plist)
        subprocess.run(["launchctl", "load", str(LAUNCH_AGENT_PATH)], check=False)
    else:
        if LAUNCH_AGENT_PATH.exists():
            subprocess.run(["launchctl", "unload", str(LAUNCH_AGENT_PATH)], check=False)
            LAUNCH_AGENT_PATH.unlink()


# ── Menu bar icon ──────────────────────────────────────────────────────────

def _make_menubar_icon():
    """
    Build an NSImage matching the Scaffold logo (3-col grid, rightmost split)
    in monochrome white, set as a template so macOS adapts it to dark/light bar.
    """
    from AppKit import NSImage, NSBezierPath, NSColor
    import Quartz

    W, H = 22.0, 17.0
    IW, IH = 20.0, 15.0
    sx, sy = IW / W, IH / H

    def rect(x, y_svg, w, h_svg):
        nx = x * sx
        nh = h_svg * sy
        ny = IH - (y_svg + h_svg) * sy
        r = Quartz.CGRectMake(nx, ny, w * sx, nh)
        return NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(r, 1.2, 1.2)

    image = NSImage.alloc().initWithSize_((IW, IH))
    image.lockFocus()
    for path, alpha in [
        (rect(0,   0,   6, 17  ), 1.00),
        (rect(8,   0,   6, 17  ), 0.70),
        (rect(16,  0,   6,  7.5), 0.45),
        (rect(16,  9.5, 6,  7.5), 0.25),
    ]:
        NSColor.colorWithWhite_alpha_(1.0, alpha).set()
        path.fill()
    image.unlockFocus()
    image.setTemplate_(True)
    return image


# ── Port helper ────────────────────────────────────────────────────────────

def _port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


# ── Main entry point ───────────────────────────────────────────────────────

def cmd_menubar(port: int = 7890) -> None:
    """Run Scaffold as a persistent menu bar app (no Dock icon)."""
    try:
        from AppKit import (
            NSApplication,
            NSApplicationActivationPolicyAccessory,
            NSControlStateValueOff,
            NSControlStateValueOn,
            NSMenu,
            NSMenuItem,
            NSStatusBar,
            NSVariableStatusItemLength,
        )
        from Foundation import NSObject
    except ImportError:
        print("AppKit not available — install pyobjc-framework-Cocoa")
        sys.exit(1)

    import ApplicationServices as AS
    from scaffold.config import load_config
    import scaffold.server as srv

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    trusted = AS.AXIsProcessTrustedWithOptions(None)
    if not trusted:
        print("Scaffold needs Accessibility permission.")
        print(f"Python: {sys.executable}")
        AS.AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
        print("Grant access in System Settings, then use the menu bar icon.")

    class _Delegate(NSObject):
        def applicationDidFinishLaunching_(self, _notification):
            self._port = port
            self._server_started = False

            item = NSStatusBar.systemStatusBar().statusItemWithLength_(
                NSVariableStatusItemLength
            )
            item.button().setImage_(_make_menubar_icon())
            item.button().setToolTip_("Scaffold")

            menu = NSMenu.new()

            # Open Organizer
            open_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Open Organizer", "openOrganizer:", ""
            )
            open_item.setTarget_(self)
            menu.addItem_(open_item)

            menu.addItem_(NSMenuItem.separatorItem())

            # Open at Login toggle
            login_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Open at Login", "toggleLoginItem:", ""
            )
            login_item.setTarget_(self)
            login_item.setState_(
                NSControlStateValueOn if _login_item_enabled() else NSControlStateValueOff
            )
            menu.addItem_(login_item)

            menu.addItem_(NSMenuItem.separatorItem())

            # Quit
            quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Quit Scaffold", "terminate:", ""
            )
            menu.addItem_(quit_item)

            item.setMenu_(menu)
            self._status_item = item  # strong ref

        def openOrganizer_(self, _sender):
            url = f"http://localhost:{self._port}/organize"
            if _port_in_use(self._port):
                subprocess.run(["open", url], check=False)
                return
            if not self._server_started:
                srv._config = load_config()
                threading.Thread(
                    target=lambda: srv.run_server(self._port), daemon=True
                ).start()
                self._server_started = True
            threading.Timer(
                0.6, lambda: subprocess.run(["open", url], check=False)
            ).start()

        def toggleLoginItem_(self, sender):
            from AppKit import NSControlStateValueOn, NSControlStateValueOff
            enabled = not _login_item_enabled()
            _set_login_item(enabled, self._port)
            sender.setState_(
                NSControlStateValueOn if enabled else NSControlStateValueOff
            )

    delegate = _Delegate.new()
    app.setDelegate_(delegate)
    print("Scaffold running in menu bar. Press Ctrl+C to quit.")
    app.run()
