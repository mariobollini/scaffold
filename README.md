# Scaffold

**Tame window chaos on an ultrawide monitor.**

If you're running many AI agents, terminals, browsers, and monitoring tools simultaneously on a large display, Scaffold keeps every window exactly where it belongs. Define a column grid, drag windows into zones, hit Apply — and your whole workspace snaps into place in one shot. Save it as a named profile and restore it any time.

![Scaffold Organizer UI](docs/screenshot.png)

---

## Why Scaffold

Modern AI-assisted workflows often involve a dozen or more concurrent windows: multiple agent terminals, browser tabs showing outputs, log viewers, chat interfaces, email, and monitoring dashboards — all running in parallel on a wide display. Manually dragging and resizing these every session is friction that compounds over time.

Scaffold solves this with a visual drag-and-drop organizer built specifically for ultrawide monitors (tested on the Dell U4924DW 49"). You define a column grid, split columns into top/bottom rows, drag your open windows into the right zones, and apply everything at once. The grid config and window layouts persist so restoring your exact setup takes one click.

---

## Features

- **Visual organizer** — browser-based drag-and-drop UI; drag window tiles into grid zones and Apply
- **Flexible column grid** — add/remove columns, merge adjacent columns, split columns into top/bottom rows
- **Layout profiles** — save and restore named snapshots of all window positions
- **Menu bar app** — lives in your menu bar with no Dock icon; optional Open at Login
- **Adjustable window gap** — slider from 0 to 32px, persisted to config
- **CLI** — `scaffold snap`, `scaffold save-layout`, `scaffold restore-layout` for scripting
- **Zero native dependencies** — pure Python + PyObjC; no Xcode or Electron required

---

## Requirements

- macOS Ventura 13+ (uses `NSScreen`, `AXUIElement`, `CGWindowList`)
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

---

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/scaffold.git
cd scaffold

# Create venv and install
uv venv
source .venv/bin/activate
uv pip install -e .

# Add to PATH (add to ~/.zshrc to make permanent)
export PATH="$PWD/.venv/bin:$PATH"
```

### First-run setup

**1. Grant Accessibility permission**

Scaffold uses the macOS Accessibility API to move windows. On first run it will prompt automatically. If it doesn't:

1. Open **System Settings → Privacy & Security → Accessibility**
2. Click **+** and add your terminal app (Terminal, iTerm2) or the Python binary
3. Enable the toggle

**2. Create your config**

```bash
mkdir -p ~/.scaffold
cp config.example.yaml ~/.scaffold/config.yaml
```

Edit `~/.scaffold/config.yaml` — set your display name and column layout. To find your display's exact name:

```bash
python3 -c "from Cocoa import NSScreen; [print(s.localizedName()) for s in NSScreen.screens()]"
```

---

## Config reference

`~/.scaffold/config.yaml`:

```yaml
display:
  name: "DELL U4924DW"   # substring matched against NSScreen.localizedName
  columns: 3             # number of columns in the grid
  gap: 8                 # pixels between zone edges
  margin: 0              # pixels inset from screen edges

zones:
  col-1:  { cols: [1],    rows: full   }   # full-height left column
  col-2:  { cols: [2],    rows: full   }   # center column
  col-3t: { cols: [3],    rows: top    }   # right column, top half
  col-3b: { cols: [3],    rows: bottom }   # right column, bottom half
```

**`cols`** — 1-indexed column numbers. `[1, 2]` spans two adjacent columns.
**`rows`** — `full`, `top` (upper half), or `bottom` (lower half).

The organizer UI can modify this config live — adding/removing columns, merging, and splitting all write back to `config.yaml` automatically.

---

## Usage

### Visual Organizer (recommended)

```bash
scaffold organize
```

Opens a browser tab with the drag-and-drop organizer.

- **Drag** window tiles from the right panel into grid zones
- **Apply** — all assigned windows snap to their zones simultaneously
- **Split** — click a zone to divide it into top/bottom rows
- **Merge** — click two adjacent zones to combine them into a wider span
- **+ / ×** — add or remove columns from the grid
- **Save / Load** — named layout profiles stored in `~/.scaffold/layouts/`
- **Window Gap slider** — adjust spacing between windows (0–32px)

**Tile-first workflow:** click a zone first, then click Split or Merge — the buttons relabel to show what will happen (Unsplit/Unmerge) before you commit.

### Menu bar app

```bash
scaffold menubar
```

Runs Scaffold as a persistent menu bar icon (no Dock icon). Menu options:
- **Open Organizer** — starts the server and opens the browser
- **Open at Login** — installs/removes a LaunchAgent so Scaffold starts at every login
- **Quit Scaffold**

### CLI commands

```bash
# Snap a window to a named zone
scaffold snap col-1                         # frontmost window → col-1
scaffold snap col-2 Terminal                # frontmost Terminal window → col-2
scaffold snap col-3t Chrome "Claude.ai"     # Chrome tab by title → top of col-3

# Layout profiles
scaffold save-layout morning                # snapshot all windows
scaffold restore-layout morning             # restore all positions
scaffold list-layouts                       # show saved profiles
```

---

## Login item (manual setup)

If you prefer not to use `scaffold menubar`, you can install a LaunchAgent directly:

```bash
# Create the plist
cat > ~/Library/LaunchAgents/com.scaffold.menubar.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.scaffold.menubar</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/.venv/bin/python</string>
    <string>-m</string>
    <string>scaffold</string>
    <string>menubar</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
EOF

# Load immediately (no restart required)
launchctl load ~/Library/LaunchAgents/com.scaffold.menubar.plist

# To unload
launchctl unload ~/Library/LaunchAgents/com.scaffold.menubar.plist
```

---

## File locations

| Path | Contents |
|------|----------|
| `~/.scaffold/config.yaml` | Zone grid, display settings, gap |
| `~/.scaffold/layouts/<name>.json` | Saved window layout profiles |
| `~/.scaffold/menubar.log` | Menu bar app stdout/stderr log |
| `~/Library/LaunchAgents/com.scaffold.menubar.plist` | Login item (if enabled) |

---

## Troubleshooting

**"No windows found"** — Click ↻ Refresh in the organizer. If still empty, check Accessibility permission (System Settings → Privacy & Security → Accessibility) and make sure your terminal or Python is listed.

**Windows don't move after Apply** — Accessibility permission may be granted for Terminal but not for the Python binary. Check `/api/debug` in the browser for diagnostics (`http://localhost:7890/api/debug`).

**Display name not matched** — Run the Python one-liner above to find the exact name, then update `display.name` in `config.yaml`.

**Organizer shows stale UI** — Hard-refresh with ⌘⇧R in Safari/Chrome to bypass cache.

**Chrome windows not matched by title** — Scaffold matches Chrome by the active tab's title. Make sure the target tab is frontmost in that window.

---

## How it works

Scaffold uses two macOS APIs:

- **Accessibility API (AXUIElement)** — reads window titles, positions, and sizes; sets position/size for each window. Requires Accessibility permission.
- **Quartz CGWindowList** — cross-references visible on-screen windows to filter out background system windows (e.g. Finder's desktop layer).

The organizer runs a local Flask/Waitress HTTP server (`localhost:7890`) serving a single-page HTML UI. Window moves happen server-side via Python when you click Apply; the browser just sends the assignment map.

---

## Contributing

Issues and PRs welcome. The codebase is intentionally small — no framework, no abstraction layers, just Python + PyObjC + a self-contained HTML file.

```
scaffold/
├── __main__.py          # CLI entry point
├── config.py            # config loading, paths
├── windows.py           # AX window enumeration and frame setting
├── zones.py             # zone geometry (column grid → pixel rects)
├── layout.py            # save/restore layout profiles
├── server.py            # Flask API server
├── static/
│   └── organizer.html   # entire organizer UI (single file)
└── cli/
    ├── organize.py      # `scaffold organize` command
    ├── menubar.py       # `scaffold menubar` command
    ├── snap.py          # `scaffold snap` command
    ├── save_layout.py
    ├── restore_layout.py
    └── list_layouts.py
```

---

## License

MIT
