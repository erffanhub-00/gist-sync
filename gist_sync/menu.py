"""The arrow-key menu: what runs when the program starts with no command."""

import shutil
import sys
from pathlib import Path

from gist_sync import __version__

from .commands import (
    cmd_auto,
    cmd_clone,
    cmd_list,
    cmd_setup,
    cmd_status,
    cmd_sync,
    create_gist_and_clone,
)
from .config import USERNAME, resolve_base_dir
from .github import check_gh, check_git, fetch_gists, folder_name_for_gist
from .gitutil import last_line, run
from .local import local_gist_map
from .output import error, fail, info, ok
from .ui import (
    ask_description,
    ask_public_or_secret,
    ask_yes_no,
    choose_option,
    pick_from_list,
    wait_for_enter,
)


def resolve_menu_path(answer, base):
    """Resolve a file/folder name the user typed in the menu.

    Accepts a full path, a path relative to the current folder,
    or just a name inside the gists folder. Returns a Path or None.
    """
    text = (answer or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if candidate.exists():
        return candidate
    in_base = base / text
    if in_base.exists():
        return in_base
    return None


def menu_about():
    """Show the About Me section with the user's social links."""
    print("About Me")
    print("  Erffan_hub")
    print("  Telegram: https://t.me/erffan_hub")
    print("  X: https://x.com/Erffanhub_00")
    print("  GitHub: https://github.com/erffanhub-00")
    print("  Gist: https://gist.github.com/erffanhub-00")


def menu_create(args, base):
    """Create a new gist from the menu: one file, or one folder.

    A folder becomes ONE gist with all its files inside, so a
    Persian + English pair stays together like git-cheatsheet.
    Files inside subfolders are NOT included: only the files
    directly in the folder become the gist. 0 goes back to the menu.
    """
    choice = choose_option(
        [
            ("1", "From one file"),
            ("2", "From a folder (all files become one gist)"),
            ("0", "Back"),
        ],
        "Create a new gist",
    )
    if choice is None or choice == "0":
        return
    if choice == "1":
        try:
            answer = input("File name (in your gists folder, or full path): ")
        except EOFError:
            return
        path = resolve_menu_path(answer, base)
        if path is None or not path.is_file():
            error("File not found. Check the name and try again.")
            return
        files = [path]
        target_name = None
        source_folder = None
    else:
        try:
            answer = input("Folder name (in your gists folder, or full path): ")
        except EOFError:
            return
        folder = resolve_menu_path(answer, base)
        if folder is None or not folder.is_dir():
            error("Folder not found. Check the name and try again.")
            return
        if (folder / ".git").is_dir():
            error("That folder is already a gist.")
            return
        files = sorted(p for p in folder.iterdir()
                       if p.is_file() and not p.name.startswith("."))
        if not files:
            error("That folder has no files in it.")
            return
        subfolders = [p for p in folder.iterdir()
                      if p.is_dir() and not p.name.startswith(".")]
        if subfolders:
            info("Files inside subfolders are not included: only the "
                 "files directly in this folder become the gist.")
        target_name = folder.name
        source_folder = folder
    secret = ask_public_or_secret()
    desc = ask_description()
    result = create_gist_and_clone(files, secret, desc, base,
                                   target_name=target_name,
                                   source_folder=source_folder)
    if result == 0 and choice == "1" and path.parent == base:
        # The file was a loose file in the gists folder: it now
        # lives inside its gist folder, so remove the loose copy
        # (same as auto mode does). Files from anywhere else
        # are left alone.
        try:
            path.unlink()
            ok(f"Removed the loose file {path.name}, "
               f"it now lives in its gist folder.")
        except OSError as exc:
            error(f"Could not remove the loose file {path.name}: {exc}")


def _remove_local_folder(base, gist):
    """Remove the local folder of a deleted gist, if it is ours.

    Returns True when a folder was removed. A folder is only
    removed when its git remote points at this gist (or it is
    not a git repo at all): a folder with the same name that
    belongs to another gist is never touched.
    """
    candidates = []
    folder = local_gist_map(base).get(gist["id"])
    if folder is not None:
        candidates.append(folder)
    name = folder_name_for_gist(gist)
    candidates.append(base / name)
    candidates.append(base / gist["id"])
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        code, out, _err = run(
            ["git", "config", "--get", "remote.origin.url"], cwd=candidate
        )
        if code == 0 and gist["id"] not in out:
            continue  # Belongs to another gist: leave it alone.
        shutil.rmtree(candidate, ignore_errors=True)
        if candidate.exists():
            error(f"Could not remove the local folder: {candidate.name}")
            return False
        ok(f"Removed the local folder: {candidate.name}")
        return True
    return False


def menu_delete(args, base):
    """Delete a gist, picked from the FRESHEST list from GitHub.

    The list is fetched from GitHub right now, never from a saved
    or local list, so it is always up to date. It shows 10 gists
    per page (n = next page, p = previous page, 0 = back) and
    only the name, no description. Deleting asks once more,
    with No as the default.
    """
    gists = fetch_gists()
    if gists is None:
        return
    if not gists:
        info("No gists found on GitHub.")
        return
    chosen = pick_from_list(
        gists,
        lambda gist: folder_name_for_gist(gist),
        title="Delete a gist (fresh list from GitHub):",
        allow_pick=True,
    )
    if chosen is None:
        return
    gist = gists[chosen]
    name = folder_name_for_gist(gist)
    print(f"  {name}")
    print(f"  https://gist.github.com/{USERNAME}/{gist['id']}")
    if not ask_yes_no("Delete this gist from GitHub?", default=False):
        info("Nothing deleted.")
        return
    code, _out, err = run(["gh", "gist", "delete", gist["id"], "--yes"])
    if code != 0:
        fail(f"Could not delete the gist. {last_line(err)}")
        return
    ok(f"Deleted gist: {name}")
    if not _remove_local_folder(base, gist):
        info("No local folder to remove.")


def cmd_menu(args):
    """Menu mode: every command, with Back (0) everywhere.

    This is what runs when the program is started with no command.
    Auto mode is option 1 here (or the `auto` command): it never
    runs by itself when the menu opens.
    """
    if not sys.stdin.isatty():
        error("Menu mode needs a terminal. Run it in a terminal, "
              "or use auto mode instead: python3 gist_sync.py auto")
        return 1
    if not check_gh() or not check_git():
        return 1
    base = resolve_base_dir(args)
    if base is None:
        return 1
    info(f"Using folder: {base}")
    options = [
        ("1", "Auto sync"),
        ("2", "Create new gist"),
        ("3", "Delete a gist"),
        ("4", "List all gists"),
        ("5", "Clone all gists"),
        ("6", "Status"),
        ("7", "Sync all"),
        ("8", "About Me"),
        ("9", "Change gists folder"),
        ("0", "Exit"),
    ]
    while True:
        choice = choose_option(options, f"=== gist-sync {__version__} ===")
        if choice is None or choice == "0":
            return 0
        if choice == "1":
            cmd_auto(args)
        elif choice == "2":
            menu_create(args, base)
        elif choice == "3":
            menu_delete(args, base)
        elif choice == "4":
            cmd_list(args)
        elif choice == "5":
            cmd_clone(args)
        elif choice == "6":
            cmd_status(args)
        elif choice == "7":
            cmd_sync(args)
        elif choice == "8":
            menu_about()
        elif choice == "9":
            cmd_setup(args)
            # The folder may have changed: use the new choice
            # for the rest of this menu session. The old
            # folder's files are never moved by the program.
            new_base = resolve_base_dir(args)
            if new_base is not None:
                base = new_base
                info(f"Using folder: {base}")
        wait_for_enter()
