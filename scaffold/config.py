import sys
import yaml
from pathlib import Path

SCAFFOLD_DIR = Path.home() / ".scaffold"
CONFIG_PATH  = SCAFFOLD_DIR / "config.yaml"
LAYOUTS_DIR  = SCAFFOLD_DIR / "layouts"

# Written on first run if no config exists.
# Leave display.name empty to use the primary display on any machine.
_DEFAULT_CONFIG = """\
# Scaffold configuration
# Edit display.name to match your monitor (or leave empty for primary display).
# The organizer UI can modify columns, gaps, and zone layout interactively.

display:
  name: ""      # substring match against display name; empty = primary display
  columns: 4    # number of columns in the grid
  gap: 8        # pixels between zone edges
  margin: 0     # pixels inset from screen edges

# Zone definitions — cols are 1-indexed, rows: full | top | bottom
# This default gives 3 full columns and a right column split into top/bottom.
zones:
  col-1:  { cols: [1], rows: full   }
  col-2:  { cols: [2], rows: full   }
  col-3:  { cols: [3], rows: full   }
  col-4t: { cols: [4], rows: top    }
  col-4b: { cols: [4], rows: bottom }
"""


def _create_default_config() -> None:
    SCAFFOLD_DIR.mkdir(parents=True, exist_ok=True)
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(_DEFAULT_CONFIG)
    print(f"Created default config at {CONFIG_PATH}")
    print("Edit display.name to match your monitor if needed, then reopen the organizer.")


def load_config() -> dict:
    """Load ~/.scaffold/config.yaml, creating it from defaults if absent."""
    if not CONFIG_PATH.exists():
        _create_default_config()

    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        print(f"Config is invalid (expected a YAML mapping): {CONFIG_PATH}")
        sys.exit(1)

    for field in ("display", "zones"):
        if field not in config:
            print(f"Config missing required top-level key: '{field}'")
            sys.exit(1)

    display = config["display"]
    if "columns" not in display:
        print("Config display section missing required key: 'columns'")
        sys.exit(1)

    if not config["zones"]:
        print("Config 'zones' section is empty — define at least one zone.")
        sys.exit(1)

    # Ensure layouts directory exists
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)

    return config


def get_layouts_dir() -> Path:
    return LAYOUTS_DIR
