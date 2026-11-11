#!/usr/bin/env python3
"""Manage GitHub Gists from one folder, with clean error handling.

Usage (run from the VS Code integrated terminal):
    python3 gist_sync.py list
    python3 gist_sync.py clone
    python3 gist_sync.py status
    python3 gist_sync.py sync
    python3 gist_sync.py create my-file.md --desc "My gist" [--secret]

Rules:
  - One folder: ~/gists (or --base-dir). Each gist is one subfolder.
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
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

USERNAME = "erffanhub-00"
DEFAULT_BASE = Path.home() / "gists"

# Friendly folder names for the 6 current gists.
# Files inside each folder are NOT renamed, only the folder is.
FRIENDLY_FOLDERS = {
    "91ca6cf9": "hermes",
    "d8f29163": "tree-prompt",
    "25a903f2ee822b97c9132ef0e80186f1": "git-cheatsheet",
    "7fcbf8721443ea30143bc76d40c21747": "linux-cheatsheet",
    "708d3c1617d9d044873536179f878c36": "powershell-cheatsheet",
    "2c1ba425a3ca0b937937368e94b9cb46": "docker-cheatsheet",
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
    """Return a list of {'id': ..., 'description': ...}, or None on error."""
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
        gists.append(
            {"id": str(item["id"]), "description": str(item.get("description") or "")}
        )
    return gists


def folder_name_for(gist_id):
    """Friendly folder name for a known gist, else the gist id itself."""
    return FRIENDLY_FOLDERS.get(gist_id, gist_id)


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
        print(f"  {gist['id']}  {folder_name_for(gist['id'])}  {desc}")
    return 0


def cmd_clone(args):
    if not check_gh() or not check_git():
        return 1
    gists = fetch_gists()
    if gists is None:
        return 1
    base = args.base_dir
    base.mkdir(parents=True, exist_ok=True)
    cloned = skipped = failed = 0
    for gist in gists:
        target = base / folder_name_for(gist["id"])
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
    base = args.base_dir
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
    base = args.base_dir
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
    cmd = ["gh", "gist", "create"]
    # File names are passed exactly as given, so the gist keeps them.
    cmd.extend(args.files)
    cmd.append("--secret" if args.secret else "--public")
    if args.desc:
        cmd.extend(["--desc", args.desc])
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
    # Clone it locally so it can be managed like the others.
    # Folder name comes from the first file you gave, not renamed.
    base = args.base_dir
    base.mkdir(parents=True, exist_ok=True)
    folder = Path(args.files[0]).stem or gist_id
    target = base / folder
    if target.is_dir():
        target = base / gist_id
    if target.is_dir():
        info(f"Local folder already exists: {target}")
        return 0
    code, _out, err = run(["gh", "gist", "clone", gist_id, str(target)])
    if code != 0:
        fail(f"Created on GitHub, but clone failed. {last_line(err)}")
        info("Run: python3 gist_sync.py clone  to fetch it locally.")
        return 1
    ok(f"Cloned locally to: {target}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="gist_sync.py",
        description="Manage your GitHub Gists from one folder (~/gists).",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE,
        help="Folder holding all gist folders (default: ~/gists).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show the full error traceback on unexpected errors.",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_list = sub.add_parser("list", help="List all your gists on GitHub.")
    p_list.set_defaults(func=cmd_list)

    p_clone = sub.add_parser("clone", help="Clone all your gists into ~/gists.")
    p_clone.set_defaults(func=cmd_clone)

    p_status = sub.add_parser(
        "status", help="Show which local gists have unpushed changes."
    )
    p_status.set_defaults(func=cmd_status)

    p_sync = sub.add_parser(
        "sync", help="Commit and push every changed gist in ~/gists."
    )
    p_sync.set_defaults(func=cmd_sync)

    p_create = sub.add_parser("create", help="Create a new gist from file(s).")
    p_create.add_argument("files", nargs="+", help="File(s) to put in the gist.")
    p_create.add_argument("--desc", default="", help="Description for the gist.")
    p_create.add_argument(
        "--secret",
        action="store_true",
        help="Create a secret (unlisted) gist. Default is public.",
    )
    p_create.set_defaults(func=cmd_create)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
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
