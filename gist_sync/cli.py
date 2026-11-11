"""Argument parsing and the entry point.

Usage (run from the VS Code integrated terminal):
    python3 gist_sync.py
        No command: menu mode. Every command is an option:
        Auto sync, Create, Delete, List, Clone, Status, Sync,
        About Me, Change gists folder. On a terminal you move
        with the up/down arrow keys and confirm with Enter;
        otherwise type the number.
    python3 gist_sync.py auto
        Auto mode: detects what changed, what is new, what was
        deleted, and what is missing locally, shows one short
        summary, asks once, and does it all. Also menu option 1.
    python3 gist_sync.py menu
        Same menu as running with no command.
    python3 gist_sync.py setup
    python3 gist_sync.py list
    python3 gist_sync.py clone
    python3 gist_sync.py status
    python3 gist_sync.py sync
    python3 gist_sync.py create my-file.md --desc "My gist" [--secret]

Rules:
  - You choose ONE folder, once, with `setup`. All your gists live
    in that folder, one subfolder per gist. The choice is saved in
    ~/.config/gist-sync/config.json, so you never type the path again.
    `--base-dir` only overrides it for a single run.
  - File names are NEVER renamed. Files inside a gist keep exactly
    the name they have on GitHub, or the name you gave the file
    when you created the gist. When a gist is cloned from GitHub,
    the program asks for its folder name and shows its own
    suggestion as the default: press Enter to accept it, or type
    a name you like better. When a gist is created from a file or
    folder you already have, no name is asked: the folder keeps
    the file's or folder's name.
  - All output is in English, so it renders correctly in the terminal.
    The menu and status lines use colors when the output is a
    terminal; piped output stays plain.
  - No token is stored in this program. It uses your `gh` login.
  - Standard library only. No pip install needed.

Requires: `gh` (github-cli) and `git`, both already on Omarchy
via `sudo pacman -S github-cli git`, plus `gh auth login`.
"""

import argparse
import sys
from pathlib import Path

from gist_sync import __version__

from .commands import (
    cmd_auto,
    cmd_clone,
    cmd_create,
    cmd_list,
    cmd_setup,
    cmd_status,
    cmd_sync,
)
from .menu import cmd_menu
from .output import error


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gist_sync.py",
        description="Manage your GitHub Gists from one folder you choose. "
        "Run with no command to open the menu.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Folder holding all gist folders, for this run only. "
        "Without it, the folder saved by 'setup' is used.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show the full error traceback on unexpected errors.",
    )
    # --base-dir also works after the command (for example
    # `sync --base-dir ~/other`), so define it on every subcommand too.
    # SUPPRESS means it only overwrites the top-level value when given.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--base-dir",
        type=Path,
        default=argparse.SUPPRESS,
        help="Folder holding all gist folders, for this run only.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_setup = sub.add_parser(
        "setup",
        parents=[common],
        help="Choose the folder that holds all your gists (asked once, saved).",
    )
    p_setup.add_argument(
        "folder",
        nargs="?",
        type=Path,
        default=None,
        help="Folder to use. If omitted, you will be asked.",
    )
    p_setup.set_defaults(func=cmd_setup)

    p_list = sub.add_parser(
        "list", parents=[common], help="List all your gists on GitHub."
    )
    p_list.set_defaults(func=cmd_list)

    p_clone = sub.add_parser(
        "clone",
        parents=[common],
        help="Clone all your gists into your chosen folder.",
    )
    p_clone.set_defaults(func=cmd_clone)

    p_status = sub.add_parser(
        "status",
        parents=[common],
        help="Show which local gists have unpushed changes.",
    )
    p_status.set_defaults(func=cmd_status)

    p_sync = sub.add_parser(
        "sync",
        parents=[common],
        help="Commit and push every changed gist in your chosen folder.",
    )
    p_sync.set_defaults(func=cmd_sync)

    p_create = sub.add_parser(
        "create", parents=[common], help="Create a new gist from file(s)."
    )
    p_create.add_argument("files", nargs="+", help="File(s) to put in the gist.")
    p_create.add_argument("--desc", default="", help="Description for the gist.")
    p_create.add_argument(
        "--secret",
        action="store_true",
        help="Create a secret (unlisted) gist. Default is public.",
    )
    p_create.set_defaults(func=cmd_create)

    p_menu = sub.add_parser(
        "menu",
        parents=[common],
        help="Menu mode: Auto sync, Create, Delete, List, Clone, "
        "Status, Sync, About Me, Change folder.",
    )
    p_menu.set_defaults(func=cmd_menu)

    p_auto = sub.add_parser(
        "auto",
        parents=[common],
        help="Auto mode: detect changes and sync (also menu option 1).",
    )
    p_auto.set_defaults(func=cmd_auto)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # No command given: open the menu (auto never runs
        # by itself; it is menu option 1, or the `auto` command).
        args.func = cmd_menu
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except Exception as exc:  # Unexpected error: no traceback by default.
        if args.debug:
            raise
        error(f"Unexpected error: {exc}")
        error("Run again with --debug to see the full error.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
