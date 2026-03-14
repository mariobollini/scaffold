"""
Zone geometry: convert YAML zone definitions into pixel rects (AX coordinate space).

Coordinate systems
------------------
NSScreen:   origin (0,0) at bottom-left of primary display; y increases upward.
AX API:     origin (0,0) at top-left of primary display; y increases downward.

Conversion for a rect computed in NSScreen coords:
    ax_y = primary_screen_height - ns_y - zone_height
"""

import sys
from Cocoa import NSScreen


def _find_screen(display_name: str | None):
    """Return the NSScreen matching display_name (substring match), or the main screen."""
    if display_name:
        for screen in NSScreen.screens():
            name = screen.localizedName() if hasattr(screen, "localizedName") else ""
            if display_name.lower() in name.lower():
                return screen
    return NSScreen.mainScreen()


def compute_zone_rect(
    zone_cfg: dict,
    screen_frame,
    primary_height: float,
    num_cols: int,
    gap: int = 8,
    margin: int = 0,
) -> tuple[int, int, int, int]:
    """
    Return (ax_x, ax_y, width, height) for one zone.

    screen_frame    NSRect from NSScreen.frame()
    primary_height  Height of the primary screen (for NSScreen→AX y-flip)
    num_cols        Total number of columns in the grid
    gap             Pixels between zone edges
    margin          Pixels inset from screen edges
    """
    sw = screen_frame.size.width
    sh = screen_frame.size.height
    ox = screen_frame.origin.x
    oy = screen_frame.origin.y

    # Column width (equal divisions after removing margins and gaps)
    usable_w = sw - 2 * margin - (num_cols - 1) * gap
    col_w = usable_w / num_cols

    cols = zone_cfg["cols"]
    c_min, c_max = min(cols), max(cols)

    # Horizontal rect (same in both coord systems)
    x = ox + margin + (c_min - 1) * (col_w + gap)
    w = (c_max - c_min + 1) * col_w + (c_max - c_min) * gap

    # Vertical rect (computed in NSScreen coords, then flipped to AX)
    rows = zone_cfg.get("rows", "full")
    usable_h = sh - 2 * margin
    half_h = (usable_h - gap) / 2

    if rows == "full":
        ns_y = oy + margin
        h = usable_h
    elif rows == "top":
        # Top half visually = higher NSScreen y
        ns_y = oy + margin + half_h + gap
        h = half_h
    elif rows == "bottom":
        # Bottom half visually = lower NSScreen y
        ns_y = oy + margin
        h = half_h
    else:
        print(f"Unknown 'rows' value: {rows!r}  (expected: full / top / bottom)")
        sys.exit(1)

    # Flip to AX coordinate space
    ax_y = primary_height - ns_y - h

    return (int(x), int(ax_y), int(w), int(h))


def get_zone_rect(zone_name: str, config: dict) -> tuple[int, int, int, int]:
    """
    Look up zone_name in config and return its AX-coordinate rect.
    Exits with a helpful error if the zone is not found.
    """
    zones = config.get("zones", {})
    if zone_name not in zones:
        available = ", ".join(sorted(zones.keys()))
        raise ValueError(
            f"Zone '{zone_name}' not found in config. Available: {available}"
        )

    zone_cfg = zones[zone_name]
    display_cfg = config.get("display", {})
    num_cols = display_cfg.get("columns", 8)
    gap = display_cfg.get("gap", 8)
    margin = display_cfg.get("margin", 0)
    display_name = display_cfg.get("name")

    screen = _find_screen(display_name)
    screen_frame = screen.frame()
    primary_height = NSScreen.mainScreen().frame().size.height

    return compute_zone_rect(zone_cfg, screen_frame, primary_height, num_cols, gap, margin)
