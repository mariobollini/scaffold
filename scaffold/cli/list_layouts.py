from scaffold.config import load_config
from scaffold.layout import list_layouts


def cmd_list_layouts() -> None:
    load_config()  # validates config exists and is well-formed
    list_layouts()
