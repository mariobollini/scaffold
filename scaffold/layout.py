"""
Layout save and restore: snapshots of all visible window positions as JSON.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scaffold.config import get_layouts_dir
from scaffold.windows import list_windows, set_window_frame


def _layout_path(name: str) -> Path:
    return get_layouts_dir() / f"{name}.json"


def save_layout(name: str) -> Path:
    """
    Snapshot all visible windows to ~/.scaffold/layouts/<name>.json.
    Returns the path written.
    """
    windows = list_windows()

    entries = [
        {
            "app_name": w["app_name"],
            "title": w["title"],
            "document": w.get("document"),
            "frame": w["frame"],
        }
        for w in windows
    ]

    data = {
        "name": name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "windows": entries,
    }

    path = _layout_path(name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved layout '{name}'  ({len(entries)} windows)  →  {path}")
    return path


def restore_layout(name: str) -> None:
    """
    Re-position all windows from a saved layout.
    Skips any window that can no longer be found; logs a warning instead of aborting.
    """
    path = _layout_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Layout '{name}' not found: {path}")

    with open(path) as f:
        data = json.load(f)

    live_windows = list_windows()

    ok_count = 0
    skip_count = 0

    for entry in data.get("windows", []):
        app = entry["app_name"]
        title = entry.get("title", "")
        frame = entry["frame"]

        # Try to find a live window matching app + title substring
        match = None
        for w in live_windows:
            if w["app_name"].lower() != app.lower():
                continue
            # Use document URL for Chrome if available
            saved_doc = entry.get("document")
            if saved_doc and w.get("document"):
                if saved_doc.lower() in w["document"].lower():
                    match = w
                    break
            # Fall back to title substring
            if title and title.lower() in w["title"].lower():
                match = w
                break
            # Last resort: same app, title both empty
            if not title and not w["title"]:
                match = w
                break

        if match is None:
            print(f"  [skip]  {app!r}  /  {title!r}")
            skip_count += 1
            continue

        ok, err = set_window_frame(
            match["ax_element"],
            frame["x"], frame["y"], frame["w"], frame["h"],
        )
        if ok:
            print(f"  [ok]    {app}  /  {match['title']!r}")
            ok_count += 1
        else:
            print(f"  [err]   {app!r}  /  {title!r}  —  {err}")
            skip_count += 1

    total = ok_count + skip_count
    print(f"\nRestored {ok_count}/{total} windows from layout '{name}'")


def list_layouts() -> None:
    """Print all saved layout names with timestamps and window counts."""
    layouts_dir = get_layouts_dir()
    files = sorted(layouts_dir.glob("*.json"))

    if not files:
        print("No saved layouts found in", layouts_dir)
        return

    name_w = max(len(p.stem) for p in files)
    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
            ts = data.get("timestamp", "unknown")
            count = len(data.get("windows", []))
            print(f"  {path.stem:<{name_w}}  {ts}  ({count} windows)")
        except Exception:
            print(f"  {path.stem:<{name_w}}  [corrupt or unreadable]")
