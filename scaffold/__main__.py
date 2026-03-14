import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="scaffold",
        description="Ultrawide window manager for macOS",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # snap
    p_snap = sub.add_parser("snap", help="Snap a window to a named zone")
    p_snap.add_argument("zone", help="Zone name from config")
    p_snap.add_argument("app", nargs="?", default=None, help="App name filter")
    p_snap.add_argument("title", nargs="?", default=None, help="Window title substring filter")

    # save-layout
    p_save = sub.add_parser("save-layout", help="Save current window layout to disk")
    p_save.add_argument("name", help="Layout name (used as filename)")

    # restore-layout
    p_restore = sub.add_parser("restore-layout", help="Restore a saved window layout")
    p_restore.add_argument("name", help="Layout name to restore")

    # list-layouts
    sub.add_parser("list-layouts", help="List all saved layouts")

    # organize
    p_org = sub.add_parser("organize", help="Open the visual drag-to-assign organizer")
    p_org.add_argument("--port", type=int, default=7890, help="Local port (default: 7890)")
    p_org.add_argument("--no-open", action="store_true", help="Don't auto-open the browser")

    # menubar
    p_mb = sub.add_parser("menubar", help="Run Scaffold as a persistent menu bar app")
    p_mb.add_argument("--port", type=int, default=7890, help="Local port (default: 7890)")

    args = parser.parse_args()

    if args.command == "snap":
        from scaffold.cli.snap import cmd_snap
        cmd_snap(args.zone, args.app, args.title)

    elif args.command == "save-layout":
        from scaffold.cli.save_layout import cmd_save_layout
        cmd_save_layout(args.name)

    elif args.command == "restore-layout":
        from scaffold.cli.restore_layout import cmd_restore_layout
        cmd_restore_layout(args.name)

    elif args.command == "list-layouts":
        from scaffold.cli.list_layouts import cmd_list_layouts
        cmd_list_layouts()

    elif args.command == "organize":
        from scaffold.cli.organize import cmd_organize
        cmd_organize(port=args.port, no_open=args.no_open)

    elif args.command == "menubar":
        from scaffold.cli.menubar import cmd_menubar
        cmd_menubar(port=args.port)


if __name__ == "__main__":
    main()
