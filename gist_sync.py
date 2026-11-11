#!/usr/bin/env python3
"""Manage GitHub Gists from one folder, with clean error handling.

Usage (run from the VS Code integrated terminal):
    python3 gist_sync.py
        No command: menu mode. Only the essential tasks (Auto sync,
        Create, Delete, About Me, Change gists folder), with Back
        (0) everywhere.
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
    when you created the gist. Only the *folder* name is friendly
    (for example "linux-cheatsheet" instead of the gist id).
  - All output is in English, so it renders correctly in the terminal.
  - No token is stored in this file. It uses your `gh` login.
  - Standard library only. No pip install needed.

Requires: `gh` (github-cli) and `git`, both already on Omarchy
via `sudo pacman -S github-cli git`, plus `gh auth login`.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

__version__ = "1.4.0"

USERNAME = "erffanhub-00"
DEFAULT_BASE = Path.home() / "gists"
CONFIG_PATH = Path.home() / ".config" / "gist-sync" / "config.json"

# Friendly folder names for the 7 older gists.
# Keys are the FULL 32-character gist ids GitHub returns.
# (v1.1.0 used short 8-character ids for Hermes and Tree, which is
# why those two cloned under their full ids instead. Fixed in v1.1.1.)
# This table is ONLY for these older gists. A gist created later
# does NOT need an entry here: when cloning, its folder name comes
# from the files inside the gist (see folder_name_for_gist).
# Files inside each folder are NOT renamed, only the folder is.
FRIENDLY_FOLDERS = {
    "91ca6cf9de61fbd124926103387507f8": "hermes",
    "d8f291636141e097d66f2a93a3982cbe": "tree-prompt",
    "25a903f2ee822b97c9132ef0e80186f1": "git-cheatsheet",
    "7fcbf8721443ea30143bc76d40c21747": "linux-cheatsheet",
    "708d3c1617d9d044873536179f878c36": "powershell-cheatsheet",
    "2c1ba425a3ca0b937937368e94b9cb46": "docker-cheatsheet",
    "b9defe688de21764d08e613a68953836": "omarchy-guide",
}


def info(message):
    print(f"[INFO] {message}")


def ok(message):
    print(f"[OK] {message}")


def skip(message):
    print(f"[SKIP] {message}")


def fail(message):
    print(f"[FAIL] {message}")


def error(message):
    print(f"[ERROR] {message}", file=sys.stderr)


def expand_folder(text):
    """Expand ~ and environment variables, return an absolute Path.

    Accepts a string or a Path (argparse gives us Paths).
    """
    return Path(os.path.expandvars(str(text).strip())).expanduser().resolve()


def load_config():
    """Saved choice from ~/.config/gist-sync/config.json, or {}.

    A missing file means no choice yet. A broken file is reported
    cleanly and treated as no choice, never a crash.
    """
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        error(f"Could not read saved settings in {CONFIG_PATH}. Ignoring it.")
        error("Run: python3 gist_sync.py setup  to choose the folder again.")
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_config(base):
    """Save the chosen folder. Returns True on success."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps({"base_dir": str(base)}, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        error(f"Could not save settings to {CONFIG_PATH}: {exc}")
        return False
    return True


def validate_folder(base):
    """Return True when base can be used as the gists folder."""
    if base.exists() and not base.is_dir():
        error(f"That path is a file, not a folder: {base}")
        return False
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        error(f"Could not create folder {base}: {exc}")
        return False
    return True


def prompt_for_folder():
    """Ask the user to choose the gists folder. Returns a Path or None.

    Pressing Enter accepts the default ~/gists. When there is no
    terminal to ask in (for example a script), the default is used
    without asking, so the program never hangs waiting for input.
    """
    if not sys.stdin.isatty():
        return DEFAULT_BASE
    print(f"Your gists will live in one folder. Each gist is one subfolder.")
    try:
        answer = input(
            f"Which folder should hold all your gists? [{DEFAULT_BASE}] "
        ).strip()
    except EOFError:
        return DEFAULT_BASE
    if not answer:
        return DEFAULT_BASE
    return expand_folder(answer)


def resolve_base_dir(args, prompt=True):
    """Work out which folder to use, in this order.

    1. --base-dir on this run (does not change the saved choice).
    2. The saved choice from setup.
    3. Ask once with setup's prompt and save the answer
       (or the default ~/gists when there is no terminal).
    Returns a Path, or None when no folder could be chosen.
    """
    if getattr(args, "base_dir", None) is not None:
        base = expand_folder(args.base_dir)
        if not validate_folder(base):
            return None
        return base
    had_config_file = CONFIG_PATH.exists()
    saved = load_config().get("base_dir")
    if saved:
        base = expand_folder(saved)
        if not validate_folder(base):
            return None
        return base
    if not prompt:
        return DEFAULT_BASE
    base = prompt_for_folder()
    if base is None:
        return None
    if not validate_folder(base):
        return None
    # Only save a fresh choice. A broken config file is left alone
    # so setup can fix it, instead of silently overwriting it.
    if not had_config_file and save_config(base):
        info(f"Saved your gists folder: {base}")
    return base


def cmd_setup(args):
    """Choose (or change) the folder that holds all your gists."""
    saved = load_config().get("base_dir")
    if saved:
        info(f"Current gists folder: {saved}")
    if getattr(args, "folder", None) is not None:
        base = expand_folder(args.folder)
    elif getattr(args, "base_dir", None) is not None:
        base = expand_folder(args.base_dir)
    else:
        base = prompt_for_folder()
        if base is None:
            return 1
    if not validate_folder(base):
        return 1
    if not save_config(base):
        return 1
    ok(f"Gists folder set to: {base}")
    info("All your gists will live in that folder.")
    return 0


def last_line(text, limit=200):
    """Return the most useful line of command output, trimmed.

    Prefer a line that actually says what went wrong (fatal / error /
    not logged in / not found), otherwise fall back to the first line.
    Git's multi-line hints end with useless lines like "git push <name>",
    so the last line alone is not a good error message.
    """
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    keywords = ("fatal", "error", "failed", "not logged", "not found",
                "no configured", "denied", "unauthorized", "timeout")
    for line in lines:
        lowered = line.lower()
        if any(word in lowered for word in keywords):
            return line[:limit]
    return lines[0][:limit]


def unpushed_count(path):
    """Number of local commits not yet pushed, or None if unknown.

    Returns 0 when up to date, >0 when commits are waiting to be pushed,
    and None when there is no upstream to compare with (for example a
    repo with no remote yet). None is treated as "needs a push attempt".
    """
    code, out, _err = run(["git", "rev-list", "--count", "@{u}..HEAD"], cwd=path)
    if code != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def run(cmd, cwd=None, timeout=120):
    """Run a command. Never raises for a missing command or timeout.

    Returns (returncode, stdout, stderr). returncode -1 means the
    command could not be started at all.
    """
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "command timed out"
    except OSError as exc:
        return -1, "", str(exc)


def check_gh():
    """Return True when gh is installed and logged in, else print why."""
    if shutil.which("gh") is None:
        error("gh is not installed.")
        error("Install it with: sudo pacman -S github-cli")
        error("Then log in with: gh auth login")
        return False
    code, _out, err = run(["gh", "auth", "status"])
    if code != 0:
        error("Not logged in to GitHub.")
        error("Run: gh auth login")
        if err.strip():
            error(last_line(err))
        return False
    return True


def check_git():
    if shutil.which("git") is None:
        error("git is not installed.")
        error("Install it with: sudo pacman -S git")
        return False
    return True


def fetch_gists():
    """Return a list of {'id', 'description', 'files'}, or None on error.

    'files' is the list of file names inside the gist, as GitHub
    reports them. It is used to name the local folder of a gist
    that has no entry in FRIENDLY_FOLDERS.
    """
    code, out, err = run(["gh", "api", f"users/{USERNAME}/gists?per_page=100"])
    if code != 0:
        # Fallback: gh gist list with JSON output.
        code, out, err = run(
            ["gh", "gist", "list", "--limit", "100", "--json", "id,description"]
        )
    if code != 0:
        error("Could not fetch your gists from GitHub.")
        if err.strip():
            error(last_line(err))
        else:
            error("Check your internet connection and run: gh auth status")
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        error("GitHub returned a response this program could not read.")
        return None
    if not isinstance(data, list):
        error("GitHub returned an unexpected response.")
        return None
    gists = []
    for item in data:
        if not isinstance(item, dict) or "id" not in item:
            continue
        raw_files = item.get("files")
        if isinstance(raw_files, dict):
            # gh api: files is an object keyed by file name.
            names = sorted(raw_files.keys())
        elif isinstance(raw_files, list):
            # gh gist list: files is a list of objects.
            names = sorted(
                str(entry.get("filename", ""))
                for entry in raw_files
                if isinstance(entry, dict) and entry.get("filename")
            )
        else:
            names = []
        gists.append(
            {
                "id": str(item["id"]),
                "description": str(item.get("description") or ""),
                "files": names,
            }
        )
    return gists


def folder_name_for(gist_id):
    """Friendly folder name for a known gist, else the gist id itself.

    Exact match first. As a fallback, a short id also matches when
    it is a prefix of a known full id (at least 8 characters), and
    vice versa, so old short ids keep working too.
    """
    if gist_id in FRIENDLY_FOLDERS:
        return FRIENDLY_FOLDERS[gist_id]
    for known_id, name in FRIENDLY_FOLDERS.items():
        if len(gist_id) >= 8 and known_id.startswith(gist_id):
            return name
        if len(known_id) >= 8 and gist_id.startswith(known_id):
            return name
    return gist_id


def folder_name_for_gist(gist):
    """Friendly folder name for a gist dict from fetch_gists.

    1. The FRIENDLY_FOLDERS table (the 7 older gists).
    2. Otherwise the files inside the gist: one file -> its name
       without the extension (my-guide.md -> my-guide); several
       files -> their common name part (guide-fa + guide-en ->
       guide). So a gist created on the GitHub website, never
       added to the table, still clones into a readable folder
       instead of its 32-character id. No table update needed.
    3. Otherwise the gist id itself.
    """
    name = folder_name_for(gist["id"])
    if name != gist["id"]:
        return name
    stems = [Path(name).stem for name in (gist.get("files") or []) if name]
    if not stems:
        return gist["id"]
    if len(stems) == 1:
        return stems[0]
    prefix = os.path.commonprefix(stems).rstrip("-_.")
    if len(prefix) >= 3:
        return prefix
    return stems[0]


def local_gists(base):
    """Subfolders of base that are git repos, sorted by name."""
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.iterdir() if p.is_dir() and (p / ".git").is_dir()
    )


def cmd_list(args):
    if not check_gh():
        return 1
    gists = fetch_gists()
    if gists is None:
        return 1
    if not gists:
        info("No gists found.")
        return 0
    print(f"Gists for {USERNAME} ({len(gists)}):")
    for gist in gists:
        desc = gist["description"] or "(no description)"
        print(f"  {gist['id']}  {folder_name_for_gist(gist)}  {desc}")
    return 0


def cmd_clone(args):
    if not check_gh() or not check_git():
        return 1
    gists = fetch_gists()
    if gists is None:
        return 1
    base = resolve_base_dir(args)
    if base is None:
        return 1
    info(f"Using folder: {base}")
    base.mkdir(parents=True, exist_ok=True)
    cloned = skipped = failed = 0
    for gist in gists:
        target = base / folder_name_for_gist(gist)
        if target.is_dir():
            if (target / ".git").is_dir():
                skip(f"{target.name}: already exists")
            else:
                fail(f"{target.name}: folder exists but is not a git repo")
                failed += 1
            skipped += 1
            continue
        info(f"Cloning {target.name} ({gist['id']}) ...")
        code, _out, err = run(["gh", "gist", "clone", gist["id"], str(target)])
        if code != 0:
            fail(f"{target.name}: clone failed. {last_line(err)}")
            failed += 1
        else:
            ok(f"{target.name}: cloned")
            cloned += 1
    print(f"Done: {cloned} cloned, {skipped} skipped, {failed} failed.")
    return 1 if failed else 0


def cmd_status(args):
    if not check_git():
        return 1
    base = resolve_base_dir(args)
    if base is None:
        return 1
    info(f"Using folder: {base}")
    gists = local_gists(base)
    if not gists:
        info(f"No local gists found in {base}.")
        info("Run: python3 gist_sync.py clone")
        return 0
    for path in gists:
        code, out, err = run(["git", "status", "--porcelain"], cwd=path)
        if code != 0:
            fail(f"{path.name}: could not check status. {last_line(err)}")
            continue
        changed = [line for line in out.splitlines() if line.strip()]
        ahead = unpushed_count(path)
        if not changed and (ahead == 0):
            print(f"[CLEAN] {path.name}")
        else:
            if changed:
                print(f"[CHANGED] {path.name}: {len(changed)} file(s)")
                for line in changed[:5]:
                    # Keep the file name exactly as git reports it.
                    print(f"    {line.strip()}")
                if len(changed) > 5:
                    print(f"    ... and {len(changed) - 5} more")
            if ahead is None:
                print(f"[UNPUSHED] {path.name}: has commits, no upstream to compare")
            elif ahead > 0:
                print(f"[UNPUSHED] {path.name}: {ahead} commit(s) not pushed yet")
    return 0


def sync_one(path):
    """Sync one gist folder. Returns 'ok', 'skip' or 'fail'.

    A failed push must not lose the change: if the commit succeeded
    but the push failed, the next run still sees the commit as
    unpushed (via unpushed_count) and retries the push.
    """
    name = path.name
    code, out, err = run(["git", "status", "--porcelain"], cwd=path)
    if code != 0:
        fail(f"{name}: could not check status. {last_line(err)}")
        return "fail"
    committed = False
    if out.strip():
        code, _out, err = run(["git", "add", "-A"], cwd=path)
        if code != 0:
            fail(f"{name}: git add failed. {last_line(err)}")
            return "fail"
        # Nothing staged (for example only ignored files changed).
        code, _out, _err = run(["git", "diff", "--cached", "--quiet"], cwd=path)
        if code != 0:
            message = f"auto update: {datetime.now():%Y-%m-%d %H:%M}"
            code, _out, err = run(["git", "commit", "-m", message], cwd=path)
            if code != 0:
                fail(f"{name}: git commit failed. {last_line(err)}")
                return "fail"
            committed = True
    ahead = unpushed_count(path)
    if not committed and ahead == 0:
        skip(f"{name}: no changes")
        return "skip"
    code, _out, err = run(["git", "push"], cwd=path)
    if code != 0:
        fail(f"{name}: git push failed. {last_line(err)}")
        return "fail"
    ok(f"{name}: pushed")
    return "ok"


def cmd_sync(args):
    if not check_git():
        return 1
    base = resolve_base_dir(args)
    if base is None:
        return 1
    info(f"Using folder: {base}")
    gists = local_gists(base)
    if not gists:
        info(f"No local gists found in {base}.")
        info("Run: python3 gist_sync.py clone")
        return 0
    counts = {"ok": 0, "skip": 0, "fail": 0}
    for path in gists:
        counts[sync_one(path)] += 1
    print(
        f"Done: {counts['ok']} pushed, "
        f"{counts['skip']} skipped, {counts['fail']} failed."
    )
    return 1 if counts["fail"] else 0


def cmd_create(args):
    missing = [f for f in args.files if not Path(f).is_file()]
    if missing:
        for name in missing:
            error(f"File not found: {name}")
        error("Check the file name and path, then try again.")
        return 1
    if not check_gh():
        return 1
    base = resolve_base_dir(args)
    if base is None:
        return 1
    info(f"Using folder: {base}")
    base.mkdir(parents=True, exist_ok=True)
    return create_gist_and_clone(args.files, args.secret, args.desc, base)


def ask_yes_no(question, default=True):
    """Ask a yes/no question. Enter accepts the default.

    Returns the default when there is no terminal to ask in,
    so the program never hangs waiting for input.
    """
    if not sys.stdin.isatty():
        return default
    hint = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{question} {hint} ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    if answer in ("y", "yes"):
        return True
    if answer in ("n", "no"):
        return False
    return default


def ask_public_or_secret():
    """Ask 1 for public, 2 for secret. Default is secret (safer)."""
    if not sys.stdin.isatty():
        return True
    try:
        answer = input("Public (1) or secret (2)? [2] ").strip()
    except EOFError:
        return True
    if answer == "1":
        return False
    return True


def ask_description():
    """Ask for a gist description. Enter means none."""
    if not sys.stdin.isatty():
        return ""
    try:
        return input("Description (Enter for none): ").strip()
    except EOFError:
        return ""


def create_gist_and_clone(files, secret, desc, base, target_name=None,
                          source_folder=None):
    """Create a gist from files, then clone it into base.

    The local folder is named after the first file (stem), or
    target_name when given, or the gist id when that folder already
    exists. Returns 0 on success.

    When the files came from a folder inside base (source_folder),
    that folder is moved aside while cloning, then removed: the
    cloned folder keeps the source folder's name, with the same
    files inside. If cloning fails, the source folder is moved back.
    """
    cmd = ["gh", "gist", "create"]
    cmd.extend(str(f) for f in files)
    # gh has NO --secret flag: secret is its default.
    if not secret:
        cmd.append("--public")
    if desc:
        cmd.extend(["--desc", desc])
    code, out, err = run(cmd)
    if code != 0:
        fail(f"Could not create gist. {last_line(err)}")
        return 1
    url = out.strip().splitlines()[-1].strip() if out.strip() else ""
    gist_id = url.rstrip("/").split("/")[-1] if url else ""
    ok(f"Created gist: {url or '(no URL returned)'}")
    if not gist_id:
        info("Run: python3 gist_sync.py clone  to fetch it locally.")
        return 0
    folder = target_name or Path(files[0]).stem or gist_id
    target = base / folder
    moved_aside = None
    if target.is_dir():
        if source_folder is not None and target == source_folder:
            # Move the source folder aside so clone can take its name.
            moved_aside = base / (".gist-sync-tmp-" + folder)
            try:
                source_folder.rename(moved_aside)
            except OSError as exc:
                error(f"Could not move the folder aside: {exc}")
                return 1
        else:
            target = base / gist_id
    if target.is_dir():
        info(f"Local folder already exists: {target}")
        return 0
    code, _out, err = run(["gh", "gist", "clone", gist_id, str(target)])
    if code != 0:
        fail(f"Created on GitHub, but clone failed. {last_line(err)}")
        info("Run: python3 gist_sync.py clone  to fetch it locally.")
        if moved_aside is not None:
            try:
                moved_aside.rename(source_folder)
            except OSError:
                pass
        return 1
    if moved_aside is not None:
        shutil.rmtree(moved_aside, ignore_errors=True)
    ok(f"Cloned locally to: {target}")
    return 0


def loose_files(base):
    """Files sitting directly in the gists folder, not in a subfolder.

    A loose file is a new gist waiting to be created. Hidden files
    (starting with a dot) are ignored.
    """
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.iterdir()
        if p.is_file() and not p.name.startswith(".")
    )


def loose_folders(base):
    """Subfolders of base that are not gists yet (no .git inside).

    A folder with files in it is a new multi-file gist waiting to
    be created: all its files become one gist. Hidden folders and
    empty folders are ignored.
    """
    if not base.is_dir():
        return []
    folders = []
    for path in sorted(base.iterdir()):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if (path / ".git").is_dir():
            continue
        files = [p for p in path.iterdir()
                 if p.is_file() and not p.name.startswith(".")]
        if files:
            folders.append((path, sorted(files)))
    return folders


def cmd_auto(args):
    """No-command mode: detect everything, ask once, do it all.

    - Gists on GitHub that are missing locally: cloned.
    - Local gist folders with changed, added or deleted files,
      or unpushed commits: synced.
    - Files sitting directly in the gists folder: offered as new
      gists, one by one. After a successful create the loose file
      is removed, because it now lives inside its gist folder.
    - Folders sitting directly in the gists folder (not gists
      yet): offered as new multi-file gists, one gist per folder.
    - Nothing to do: says so and does nothing on GitHub.
    """
    if not check_gh() or not check_git():
        return 1
    base = resolve_base_dir(args)
    if base is None:
        return 1
    info(f"Using folder: {base}")
    base.mkdir(parents=True, exist_ok=True)
    gists = fetch_gists()
    if gists is None:
        return 1

    # What is missing locally?
    missing = []
    for gist in gists:
        friendly = base / folder_name_for_gist(gist)
        by_id = base / gist["id"]
        if not ((friendly.is_dir() and (friendly / ".git").is_dir())
                or (by_id.is_dir() and (by_id / ".git").is_dir())):
            missing.append(gist)

    # What changed locally? (changed, added or deleted files,
    # or commits that were never pushed)
    changed = []
    for path in local_gists(base):
        code, out, err = run(["git", "status", "--porcelain"], cwd=path)
        if code != 0:
            fail(f"{path.name}: could not check status. {last_line(err)}")
            continue
        lines = [line for line in out.splitlines() if line.strip()]
        ahead = unpushed_count(path)
        if lines or (ahead is None) or (ahead or 0) > 0:
            changed.append((path, len(lines)))

    loose = loose_files(base)
    folders = loose_folders(base)

    if not missing and not changed and not loose and not folders:
        ok("Everything is up to date.")
        return 0

    print("Found:")
    for gist in missing:
        print(f"  {folder_name_for_gist(gist)}: missing locally, will be cloned")
    for path, count in changed:
        print(f"  {path.name}: {count} file(s) changed")
    for path in loose:
        print(f"  {path.name}: new file, not in any gist yet")
    for path, files in folders:
        print(f"  {path.name}/: new folder with {len(files)} file(s), "
              f"not a gist yet")

    if not ask_yes_no("Sync now?", default=True):
        info("Nothing changed on GitHub.")
        return 0

    failed = 0
    for gist in missing:
        target = base / folder_name_for_gist(gist)
        info(f"Cloning {target.name} ({gist['id']}) ...")
        code, _out, err = run(["gh", "gist", "clone", gist["id"], str(target)])
        if code != 0:
            fail(f"{target.name}: clone failed. {last_line(err)}")
            failed += 1
        else:
            ok(f"{target.name}: cloned")
    for path, _count in changed:
        if sync_one(path) == "fail":
            failed += 1
    for path in loose:
        if not ask_yes_no(f"Create a new gist from {path.name}?", default=True):
            skip(f"{path.name}: skipped")
            continue
        secret = ask_public_or_secret()
        desc = ask_description()
        if create_gist_and_clone([path], secret, desc, base) == 0:
            try:
                path.unlink()
                ok(f"Removed the loose file {path.name}, "
                   f"it now lives in its gist folder.")
            except OSError as exc:
                error(f"Could not remove the loose file {path.name}: {exc}")
        else:
            failed += 1
    for path, files in folders:
        label = f"{path.name}/ ({len(files)} file(s))"
        if not ask_yes_no(f"Create a new gist from {label}?", default=True):
            skip(f"{path.name}: skipped")
            continue
        secret = ask_public_or_secret()
        desc = ask_description()
        if create_gist_and_clone(files, secret, desc, base,
                                 target_name=path.name,
                                 source_folder=path) != 0:
            failed += 1
    if failed:
        print(f"Done, with {failed} failure(s).")
        return 1
    ok("Done.")
    return 0


def wait_for_enter():
    """Pause so the user can read the output, then go back to the menu."""
    if not sys.stdin.isatty():
        return
    try:
        input("Press Enter to go back to the menu. ")
    except EOFError:
        return


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
    0 goes back to the menu.
    """
    print("Create a new gist")
    print("  1. From one file")
    print("  2. From a folder (all files become one gist)")
    print("  0. Back")
    try:
        choice = input("Choose [0-2]: ").strip()
    except EOFError:
        return
    if choice == "0" or not choice:
        return
    if choice not in ("1", "2"):
        error("Choose 0, 1 or 2.")
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


def menu_delete(args, base):
    """Delete a gist, picked from the FRESHEST list from GitHub.

    The list is fetched from GitHub right now, never from a saved
    or local list, so it is always up to date. 0 goes back to the
    menu. Deleting asks once more, with No as the default.
    """
    gists = fetch_gists()
    if gists is None:
        return
    if not gists:
        info("No gists found on GitHub.")
        return
    print("Delete a gist (fresh list from GitHub):")
    for index, gist in enumerate(gists, start=1):
        name = folder_name_for_gist(gist)
        desc = gist["description"] or "(no description)"
        print(f"  {index}. {name}  {desc}")
    print("  0. Back")
    try:
        choice = input("Choose a gist to delete [0 Back]: ").strip()
    except EOFError:
        return
    if choice == "0" or not choice:
        return
    try:
        number = int(choice)
    except ValueError:
        error("Choose a number from the list.")
        return
    if not 1 <= number <= len(gists):
        error("That number is not on the list.")
        return
    gist = gists[number - 1]
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
    for folder in (base / name, base / gist["id"]):
        if folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)
            ok(f"Removed the local folder: {folder.name}")


def cmd_menu(args):
    """Menu mode: only the essential tasks, with Back (0) everywhere.

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
    while True:
        print(f"=== gist-sync {__version__} ===")
        print("  1. Auto sync")
        print("  2. Create new gist")
        print("  3. Delete a gist")
        print("  4. About Me")
        print("  5. Change gists folder")
        print("  0. Exit")
        try:
            choice = input("Choose [0-5]: ").strip()
        except EOFError:
            print()
            return 0
        if choice == "0":
            return 0
        if choice == "1":
            cmd_auto(args)
        elif choice == "2":
            menu_create(args, base)
        elif choice == "3":
            menu_delete(args, base)
        elif choice == "4":
            menu_about()
        elif choice == "5":
            cmd_setup(args)
            # The folder may have changed: use the new choice
            # for the rest of this menu session. The old
            # folder's files are never moved by the program.
            new_base = resolve_base_dir(args)
            if new_base is not None:
                base = new_base
                info(f"Using folder: {base}")
        else:
            error("Choose 0, 1, 2, 3, 4 or 5.")
            continue
        wait_for_enter()


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
        help="Menu mode: Auto sync, Create, Delete, About Me, Change folder.",
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
