from scaffold.config import load_config
from scaffold.windows import check_accessibility
from scaffold.layout import restore_layout


def cmd_restore_layout(name: str) -> None:
    check_accessibility()
    load_config()  # validates config exists and is well-formed
    restore_layout(name)
