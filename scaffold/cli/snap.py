import sys

from scaffold.config import load_config
from scaffold.zones import get_zone_rect
from scaffold.windows import check_accessibility, get_frontmost_window, find_window


def cmd_snap(zone_name: str, app_name: str | None, title_substr: str | None) -> None:
    check_accessibility()
    config = load_config()
    rect = get_zone_rect(zone_name, config)

    if app_name is None and title_substr is None:
        win = get_frontmost_window()
        if win is None:
            print("Could not identify the frontmost window.")
            sys.exit(1)
    else:
        win = find_window(app_name, title_substr)
        if win is None:
            desc = " / ".join(filter(None, [app_name, title_substr]))
            print(f"No window found matching: {desc!r}")
            sys.exit(1)

    x, y, w, h = rect
    from scaffold.windows import set_window_frame
    ok, err = set_window_frame(win["ax_element"], x, y, w, h)

    if ok:
        label = f"{win['app_name']}"
        if win["title"]:
            label += f"  /  {win['title']!r}"
        print(f"Snapped  {label}")
        print(f"  zone: {zone_name}  →  {w}×{h} @ ({x}, {y})")
    else:
        print(f"Failed to snap window to zone '{zone_name}': {err}")
        sys.exit(1)
