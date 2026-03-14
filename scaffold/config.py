import sys
import yaml
from pathlib import Path

SCAFFOLD_DIR = Path.home() / ".scaffold"
CONFIG_PATH = SCAFFOLD_DIR / "config.yaml"
LAYOUTS_DIR = SCAFFOLD_DIR / "layouts"


def load_config() -> dict:
    """Load and validate ~/.scaffold/config.yaml. Exits with a clear error on failure."""
    if not CONFIG_PATH.exists():
        print(f"Config not found: {CONFIG_PATH}")
        print()
        print("Create ~/.scaffold/config.yaml — see config.example.yaml in the project repo.")
        sys.exit(1)

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

    # Ensure the layouts directory exists
    LAYOUTS_DIR.mkdir(parents=True, exist_ok=True)

    return config


def get_layouts_dir() -> Path:
    return LAYOUTS_DIR
