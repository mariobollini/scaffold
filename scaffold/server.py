"""
Flask backend for the visual organizer panel.
Serves organizer.html and REST endpoints for window/zone data and snap execution.
"""

import hashlib
import logging
import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_file

app = Flask(__name__)
logging.getLogger("waitress").setLevel(logging.ERROR)

# Module-level state set by cmd_organize before the server starts
_config: dict | None = None
_windows_cache: dict = {}        # wid -> window dict (refreshed per /api/windows call)
_apply_done_time: float | None = None
_last_ping_time: float = time.time()


# ── Helpers ───────────────────────────────────────────────────────────────

def _unique_wids(windows: list[dict]) -> list[tuple[str, dict]]:
    """Assign a unique wid string to each window (handles duplicate app+title)."""
    seen: dict[str, int] = {}
    result = []
    for w in windows:
        base = hashlib.md5(f"{w['app_name']}|{w['title']}".encode()).hexdigest()[:12]
        count = seen.get(base, 0)
        seen[base] = count + 1
        wid = base if count == 0 else f"{base}_{count}"
        result.append((wid, w))
    return result


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return redirect("/organize")


@app.get("/organize")
def organize():
    path = Path(__file__).parent / "static" / "organizer.html"
    response = send_file(str(path))
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/windows")
def api_windows():
    global _windows_cache
    from scaffold.windows import list_windows

    # Don't pre-check accessibility — just try. If the process has inherited
    # trust from Terminal, AXIsProcessTrustedWithOptions returns False but the
    # AX calls still work. Pre-checking would block unnecessarily.
    _windows_cache = {}
    wins = list_windows()
    pairs = _unique_wids(wins)
    result = []
    for wid, w in pairs:
        _windows_cache[wid] = w
        result.append({"wid": wid, "app": w["app_name"], "title": w["title"]})

    result.sort(key=lambda x: (x["app"].lower(), x["title"].lower()))
    return jsonify(result)


@app.get("/api/display")
def api_display():
    display = _config.get("display", {})
    return jsonify({
        "gap":     display.get("gap", 8),
        "margin":  display.get("margin", 0),
        "columns": display.get("columns", 8),
    })


@app.get("/api/zones")
def api_zones():
    display = _config.get("display", {})
    num_cols = display.get("columns", 8)
    result = [
        {
            "name": name,
            "cols": cfg["cols"],
            "rows": cfg.get("rows", "full"),
            "num_cols": num_cols,
        }
        for name, cfg in _config.get("zones", {}).items()
    ]
    return jsonify(result)


@app.post("/api/apply")
def api_apply():
    global _apply_done_time, _last_ping_time, _windows_cache
    from scaffold.windows import set_window_frame, list_windows
    from scaffold.zones import get_zone_rect, compute_zone_rect
    from scaffold.zones import _find_screen
    from Cocoa import NSScreen

    # Re-enumerate windows fresh so AX element references are never stale.
    _windows_cache = {}
    for wid, w in _unique_wids(list_windows()):
        _windows_cache[wid] = w

    assignments = request.get_json() or []  # [{zone, wid, cols, rows, num_cols}, ...]
    results = []

    display_cfg = _config.get("display", {})
    gap    = display_cfg.get("gap", 8)
    margin = display_cfg.get("margin", 0)
    display_name = display_cfg.get("name")
    screen = _find_screen(display_name)
    screen_frame = screen.visibleFrame()   # excludes menu bar & dock
    primary_height = NSScreen.mainScreen().frame().size.height

    for item in assignments:
        zone_name = item["zone"]
        wid       = item["wid"]
        win       = _windows_cache.get(wid)

        if win is None:
            results.append({"zone": zone_name, "wid": wid, "status": "error", "msg": "window not found — try Refresh"})
            continue

        try:
            # Prefer inline geometry sent by the UI (works even if config zone
            # names don't match, e.g. after the config bar was edited).
            if "cols" in item and "rows" in item:
                zone_cfg = {"cols": item["cols"], "rows": item["rows"]}
                num_cols = item.get("num_cols", display_cfg.get("columns", 8))
                x, y, w, h = compute_zone_rect(
                    zone_cfg, screen_frame, primary_height, num_cols, gap, margin
                )
            else:
                x, y, w, h = get_zone_rect(zone_name, _config)

            ok, err = set_window_frame(win["ax_element"], x, y, w, h)
            results.append({
                "zone": zone_name,
                "wid":  wid,
                "status": "ok" if ok else "error",
                "msg":  err if not ok else "",
            })
        except Exception as e:
            results.append({"zone": zone_name, "wid": wid, "status": "error", "msg": str(e)})

    _apply_done_time = time.time()
    _last_ping_time = time.time()
    return jsonify(results)


@app.post("/api/save-layout")
def api_save_layout():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    try:
        from scaffold.layout import save_layout
        save_layout(name)
        return jsonify({"status": "ok", "name": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/save-grid-config")
def api_save_grid_config():
    """
    Rebuild the zones section of config.yaml from {columns, groups}.
    groups: [{cols: [1,2], split: false}, {cols: [3], split: true}, ...]
    Zone names: col-N (full), col-Nt/col-Nb (split), col-N-M (merged span).
    """
    global _config
    data = request.get_json() or {}
    columns = int(data.get("columns", 8))
    groups = data.get("groups", [])

    new_zones = {}
    for g in groups:
        cols = sorted(g["cols"])
        split = g.get("split", False)
        c_min, c_max = cols[0], cols[-1]
        base = f"col-{c_min}-{c_max}" if len(cols) > 1 else f"col-{c_min}"
        if split:
            new_zones[f"{base}t"] = {"cols": cols, "rows": "top"}
            new_zones[f"{base}b"] = {"cols": cols, "rows": "bottom"}
        else:
            new_zones[base] = {"cols": cols, "rows": "full"}

    if "gap" in data:
        _config["display"]["gap"] = int(data["gap"])
    _config["display"]["columns"] = columns
    _config["zones"] = new_zones

    import yaml
    from scaffold.config import CONFIG_PATH
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(_config, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False, indent=2)

    return jsonify({"status": "ok", "zones": list(new_zones.keys())})


@app.get("/api/debug")
def api_debug():
    """Diagnostic endpoint — call from browser to see what's happening."""
    import sys
    from scaffold.windows import check_accessibility_bool, list_windows
    import ApplicationServices as AS

    trusted_plain = AS.AXIsProcessTrustedWithOptions(None)
    ok, msg = check_accessibility_bool()

    wins = []
    try:
        wins = list_windows()
    except Exception as e:
        win_err = str(e)
    else:
        win_err = None

    return jsonify({
        "python": sys.executable,
        "pid": os.getpid(),
        "ax_trusted_plain": trusted_plain,
        "ax_trusted_with_options": ok,
        "window_count": len(wins),
        "window_error": win_err,
        "sample_windows": [
            {"app": w["app_name"], "title": w["title"]} for w in wins[:5]
        ],
    })


@app.get("/api/layouts")
def api_layouts():
    import json as _json
    from scaffold.config import get_layouts_dir
    layouts_dir = get_layouts_dir()
    result = []
    for path in sorted(layouts_dir.glob("*.json")):
        try:
            with open(path) as f:
                data = _json.load(f)
            result.append({
                "name": path.stem,
                "timestamp": data.get("timestamp", ""),
                "count": len(data.get("windows", [])),
            })
        except Exception:
            pass
    return jsonify(result)


@app.post("/api/load-layout")
def api_load_layout():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        from scaffold.layout import restore_layout
        restore_layout(name)
        return jsonify({"status": "ok", "name": name})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/ping")
def api_ping():
    global _last_ping_time
    _last_ping_time = time.time()
    return jsonify({"ok": True})


@app.post("/api/shutdown")
def api_shutdown():
    threading.Timer(0.3, lambda: os._exit(0)).start()
    return jsonify({"status": "shutting down"})



# ── Entry point ───────────────────────────────────────────────────────────

def run_server(port: int) -> None:
    """Start waitress and block until process exits."""
    from waitress import serve
    serve(app, host="127.0.0.1", port=port)
