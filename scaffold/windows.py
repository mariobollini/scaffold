"""
macOS Accessibility API bindings for window enumeration and frame manipulation.

Uses AXUIElement (pyobjc-framework-ApplicationServices) — no Xcode required.
"""

import sys
from Cocoa import NSWorkspace
import ApplicationServices as AS
import Quartz


# ---------------------------------------------------------------------------
# Permission check
# ---------------------------------------------------------------------------

def check_accessibility_bool() -> tuple[bool, str]:
    """Return (True, '') if Accessibility is granted, else (False, instructions).

    When not granted, triggers the native macOS permission prompt so the correct
    process appears in System Settings → Accessibility automatically.
    """
    if AS.AXIsProcessTrustedWithOptions(None):
        return True, ""

    # Trigger the native prompt — macOS opens System Settings with this
    # process already highlighted so the user just needs to toggle it on.
    AS.AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})

    return False, (
        "System Settings → Accessibility has opened.\n"
        "Enable the toggle for the highlighted entry, then click Apply again."
    )


def check_accessibility() -> None:
    """Exit with instructions if the Accessibility permission is not granted."""
    ok, msg = check_accessibility_bool()
    if not ok:
        print(msg)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _attr(element, attribute):
    """Return the value of an AX attribute, or None on any error."""
    err, value = AS.AXUIElementCopyAttributeValue(element, attribute, None)
    if err != AS.kAXErrorSuccess:
        return None
    return value


def _point(ax_value) -> tuple[float, float] | None:
    if ax_value is None:
        return None
    ok, pt = AS.AXValueGetValue(ax_value, AS.kAXValueCGPointType, None)
    return (pt.x, pt.y) if ok else None


def _size(ax_value) -> tuple[float, float] | None:
    if ax_value is None:
        return None
    ok, sz = AS.AXValueGetValue(ax_value, AS.kAXValueCGSizeType, None)
    return (sz.width, sz.height) if ok else None


def _window_dict(app_name: str, pid: int, win) -> dict | None:
    """Build a window info dict from an AXUIElement window. Returns None if unusable."""
    # Skip minimized windows
    minimized = _attr(win, AS.kAXMinimizedAttribute)
    if minimized:
        return None

    title = _attr(win, AS.kAXTitleAttribute) or ""
    document = _attr(win, AS.kAXDocumentAttribute)  # URL string for browsers, else None

    pos = _point(_attr(win, AS.kAXPositionAttribute))
    size = _size(_attr(win, AS.kAXSizeAttribute))
    if pos is None or size is None:
        return None

    return {
        "app_name": app_name,
        "title": title if isinstance(title, str) else "",
        "document": document if isinstance(document, str) else None,
        "pid": pid,
        "ax_element": win,
        "frame": {"x": pos[0], "y": pos[1], "w": size[0], "h": size[1]},
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_windows() -> list[dict]:
    """
    Return info dicts for all visible, non-minimized windows across all apps.
    Each dict: {app_name, title, document, pid, ax_element, frame{x,y,w,h}}
    """
    # Build set of real on-screen window IDs from Quartz (excludes the Finder
    # desktop background window, wallpaper, and other invisible system elements).
    cg_wins = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly
        | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    ) or []
    onscreen_ids = {int(w["kCGWindowNumber"]) for w in cg_wins
                    if w.get("kCGWindowLayer", 1) == 0}

    results = []
    workspace = NSWorkspace.sharedWorkspace()

    # Bundle IDs of system UI agents that are not real user windows.
    _EXCLUDED_BUNDLES = {
        "com.apple.notificationcenterui",  # Notification Center (shows on layer 0 in Tahoe)
    }

    for app in workspace.runningApplications():
        if app.bundleIdentifier() in _EXCLUDED_BUNDLES:
            continue
        pid = app.processIdentifier()
        app_name = app.localizedName() or ""
        try:
            ax_app = AS.AXUIElementCreateApplication(pid)
            err, wins = AS.AXUIElementCopyAttributeValue(ax_app, AS.kAXWindowsAttribute, None)
            if err != AS.kAXErrorSuccess or not wins:
                continue
            for win in wins:
                # Skip windows not present in the Quartz on-screen list.
                # AXWindowID matches kCGWindowNumber; if unavailable, allow through.
                win_id = _attr(win, "AXWindowID")
                if win_id is not None and int(win_id) not in onscreen_ids:
                    continue
                info = _window_dict(app_name, pid, win)
                if info:
                    results.append(info)
        except Exception:
            continue

    return results


def get_frontmost_window() -> dict | None:
    """Return info dict for the frontmost window of the active application."""
    workspace = NSWorkspace.sharedWorkspace()
    active_app = workspace.frontmostApplication()
    if not active_app:
        return None

    pid = active_app.processIdentifier()
    app_name = active_app.localizedName() or ""
    try:
        ax_app = AS.AXUIElementCreateApplication(pid)
        err, wins = AS.AXUIElementCopyAttributeValue(ax_app, AS.kAXWindowsAttribute, None)
        if err != AS.kAXErrorSuccess or not wins:
            return None
        return _window_dict(app_name, pid, wins[0])
    except Exception:
        return None


def find_window(
    app_name: str | None = None,
    title_substr: str | None = None,
    windows: list[dict] | None = None,
) -> dict | None:
    """
    Find the first window matching the given filters.

    app_name      Case-insensitive substring match against the app name.
    title_substr  Case-insensitive substring match against the window title.
    windows       Pre-fetched window list (calls list_windows() if None).
    """
    if windows is None:
        windows = list_windows()

    for win in windows:
        if app_name and app_name.lower() not in win["app_name"].lower():
            continue
        if title_substr and title_substr.lower() not in win["title"].lower():
            continue
        return win

    return None


def set_window_frame(ax_element, x: int, y: int, w: int, h: int) -> tuple[bool, str]:
    """
    Move and resize a window to (x, y, w, h) in AX coordinates.

    Pattern: position → size → position again.
    The second position set corrects drift that some apps apply after resize.

    Returns (True, "") on success, or (False, error_message) on failure.
    """
    pos_val  = AS.AXValueCreate(AS.kAXValueCGPointType, Quartz.CGPoint(x, y))
    size_val = AS.AXValueCreate(AS.kAXValueCGSizeType,  Quartz.CGSize(w, h))

    err1 = AS.AXUIElementSetAttributeValue(ax_element, AS.kAXPositionAttribute, pos_val)
    err2 = AS.AXUIElementSetAttributeValue(ax_element, AS.kAXSizeAttribute,     size_val)
    err3 = AS.AXUIElementSetAttributeValue(ax_element, AS.kAXPositionAttribute, pos_val)

    if err1 == err2 == AS.kAXErrorSuccess:
        return True, ""

    # Map the most common AX error codes to human-readable strings
    _AX_ERRORS = {
        -25200: "kAXErrorFailure",
        -25201: "kAXErrorIllegalArgument",
        -25202: "kAXErrorInvalidUIElement (stale reference — try Refresh)",
        -25205: "kAXErrorAttributeUnsupported (window can't be moved)",
        -25208: "kAXErrorCannotComplete (app unresponsive or wrong Space?)",
        -25212: "kAXErrorNotImplemented",
    }
    def _desc(e):
        return _AX_ERRORS.get(e, f"AXError {e}") if e != 0 else "ok"

    return False, f"pos={_desc(err1)} size={_desc(err2)} pos2={_desc(err3)}"
