# Scaffold — Claude Code Handoff

## What this project is

macOS window manager for ultrawide monitors. Python + PyObjC, no Electron. A Flask server runs locally; the organizer is a single-file HTML/JS SPA at `scaffold/static/organizer.html`. A menu bar app (`scaffold menubar`) wraps the server with a status bar icon and no Dock icon.

The user runs this daily for AI-assisted work involving many concurrent windows.

---

## Coordinate system (critical — easy to get wrong)

Two systems in play:

| System | Origin | Y direction |
|--------|--------|-------------|
| NSScreen | bottom-left of primary display | increases upward |
| AX API (AXUIElement) | top-left of primary display | increases downward |

Conversion in `zones.py`:
```python
ax_y = primary_height - ns_y - h
```
where `ns_y` is the **bottom** of the window rect in NSScreen coords, `h` is height, and `primary_height` is always `NSScreen.mainScreen().frame().size.height` (full frame, not visible).

**Always use `visibleFrame()` for positioning**, not `frame()`. `frame()` includes the menu bar (~38px). When a window is placed at `ax_y=0` macOS clamps it below the menu bar, but the bottom zone isn't clamped — causing the two split halves to overlap by roughly one title-bar height. Fixed in `get_zone_rect` and `api_apply`.

---

## Key files

```
scaffold/
├── windows.py        AX window enumeration; list_windows(), set_window_frame()
├── zones.py          Grid geometry — column widths, top/bottom split math
├── server.py         Flask API; /api/apply is where windows actually move
├── config.py         Config load/auto-create; paths: ~/.scaffold/config.yaml
├── layout.py         Save/restore named profiles to ~/.scaffold/layouts/
├── static/
│   └── organizer.html   Entire UI — ~1100 lines, HTML + CSS + JS, no build step
└── cli/
    ├── menubar.py    NSStatusBar app, login item (LaunchAgent), menu construction
    ├── organize.py   One-shot: start server + open browser
    └── snap.py       CLI: scaffold snap <zone> [app] [title]
```

---

## organizer.html architecture

Single file, no framework. Key JS state:

```js
state         = { zones, windows, assignments, results }
draft         = { columns, groups: [{cols, split}] }
configMode    = 'none' | 'split' | 'merge'
tileSelection = groupIdx | null   // tile-first flow
mergeSelection= groupIdx | null
resetPending  = bool
currentGap    = int
```

**Draft model**: the grid is stored as `groups` (each group = one or more merged columns, optionally split top/bottom). `zonesFromDraft()` expands this to flat zone list. `inferDraft()` reconstructs it from server zone data on load.

**Rendering flow**: any layout change → `applyDraftToGrid()` → `renderZoneGrid()` + `saveGridConfig()`. The grid is always rebuilt from scratch (`innerHTML = ''`).

**Mode UI invariant**: `_updateModeUI()` must be called whenever `configMode`, `tileSelection`, or `resetPending` changes. `applyDraftToGrid()` calls it at the top as a backstop. `addGroup()` and `deleteGroup()` reset `configMode` before calling `applyDraftToGrid()` — if they don't, the mode buttons stay lit after add/delete.

---

## zones.py — split geometry

```python
usable_h = sh - 2 * margin          # sh from visibleFrame
half_h   = (usable_h - gap) / 2

# "bottom" (lower on screen = lower NSScreen y):
ns_y = oy + margin
h    = half_h

# "top" (higher on screen = higher NSScreen y):
ns_y = oy + margin + half_h + gap
h    = half_h
```

Returns `round()` not `int()` to avoid systematic floor truncation.

---

## windows.py — macOS Tahoe notes

- In macOS Tahoe, `com.apple.notificationcenterui` windows appear on `kCGWindowLayer == 0` and leak into `list_windows()`. They are excluded by bundle ID in the `runningApplications()` loop.
- In Tahoe, `terminate:` menu items get an auto-assigned symbol image. The Quit item in `menubar.py` calls `quit_item.setImage_(None)` to strip it.

---

## Recent work (session ending 2026-03-27)

### Bugs fixed
- **Split overlap** (`zones.py`): switched `screen.frame()` → `screen.visibleFrame()` in `get_zone_rect` and `api_apply`. Menu bar clamping was causing ~38px overlap between top/bottom split zones.
- **Stale mode highlighting** (`organizer.html`): `addGroup()` / `deleteGroup()` didn't reset `configMode`; added `_updateModeUI()` call to `applyDraftToGrid()` as backstop.
- **Notification Center in window list** (`windows.py`): excluded `com.apple.notificationcenterui` by bundle ID.
- **Quit icon in menu bar** (`menubar.py`): stripped auto-assigned Tahoe symbol with `setImage_(None)`.

### Features added
- **Preserve assignments on split/merge**: `preserveAssignments()` in organizer.html matches old zones to new zones by column overlap — avoids clearing all tiles when layout changes.
- **Reset button**: in header row, two-click confirm flow. First click shows orange warning text; second executes; cancels on any other interaction.
- **Tile label hierarchy**: window name is now the primary label (18px, `#c8e0ff`) when assigned; zone name drops to small secondary (11px, `#555`). Unassigned tiles unchanged.
- **Contrast + font pass**: zone borders, text, and UI labels lifted throughout for legibility.

---

## Config and data locations

| Path | Purpose |
|------|---------|
| `~/.scaffold/config.yaml` | Zone grid, display settings, gap — rewritten by UI on any grid change |
| `~/.scaffold/layouts/<name>.json` | Named window position snapshots |
| `~/.scaffold/menubar.log` | Menu bar app stdout/stderr |
| `~/Library/LaunchAgents/com.scaffold.menubar.plist` | Login item (written by "Open at Login") |

---

## Running locally

```bash
cd ~/dev/scaffold
source .venv/bin/activate
scaffold menubar          # menu bar mode (recommended)
# or
scaffold organize         # one-shot, opens browser at localhost:7890
```

Debug endpoint: `http://localhost:7890/api/debug` — shows AX trust status, window count, sample windows.

---

## What to avoid

- Don't use `NSScreen.frame()` for window positioning — always `visibleFrame()`. `primary_height` for the y-flip is the only place `frame()` is correct.
- Don't call `applyDraftToGrid()` without first resetting `configMode` (or rely on the backstop in `applyDraftToGrid` which calls `_updateModeUI()`).
- The organizer HTML is a single file with no build step — don't introduce a bundler or split it without a good reason.
- PyObjC types (NSRect, CGPoint, etc.) don't behave like plain Python objects — access `.size.width`, `.origin.x` etc. explicitly; don't try to unpack or iterate them.
