"""The gist folders on this machine, and syncing one of them."""

import re
import shutil
from datetime import datetime
from pathlib import Path

from .gitutil import (
    commit_count,
    has_remote,
    is_whitespace_only,
    last_line,
    run,
    sync_counts,
)
from .output import error, fail, ok, skip

# There is NO table of gist ids to folder names in this file.
# A gist is recognised locally by the git remote of its folder
# (see local_gist_map), so a folder keeps working whatever it is
# called, and a new folder is named from the files inside the
# gist (see folder_name_for_gist in github.py). Nothing here ever
# needs to be updated when a gist is added.


def _iterdir_safe(base):
    """base.iterdir(), or [] when the folder cannot be read."""
    try:
        return list(base.iterdir())
    except OSError:
        return []


def local_gists(base):
    """Subfolders of base that are git repos, sorted by name."""
    if not base.is_dir():
        return []
    return sorted(
        p for p in _iterdir_safe(base)
        if p.is_dir() and (p / ".git").is_dir()
    )


def local_gist_map(base):
    """Map gist id -> local folder, from each folder's git remote.

    A gist folder is recognised by the remote it was cloned from
    (https://gist.github.com/<user>/<id>.git), NOT by its folder
    name. So a folder keeps working whatever it is called -- an
    old name like "hermes", a file-based name, or even the raw
    32-character id -- and clone/auto never make a duplicate
    copy under a different name.
    """
    mapping = {}
    for path in local_gists(base):
        code, out, _err = run(
            ["git", "config", "--get", "remote.origin.url"], cwd=path
        )
        if code != 0:
            continue
        match = re.search(r"[0-9a-f]{32}", out)
        if match:
            mapping[match.group(0)] = path
    return mapping


def loose_files(base):
    """Files sitting directly in the gists folder, not in a subfolder.

    A loose file is a new gist waiting to be created. Hidden files
    (starting with a dot) are ignored.
    """
    if not base.is_dir():
        return []
    return sorted(
        p for p in _iterdir_safe(base)
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
    for path in sorted(_iterdir_safe(base)):
        if not path.is_dir() or path.name.startswith("."):
            continue
        if (path / ".git").is_dir():
            continue
        files = [p for p in _iterdir_safe(path)
                 if p.is_file() and not p.name.startswith(".")]
        if files:
            folders.append((path, sorted(files)))
    return folders


def sync_one(path):
    """Sync one gist folder. Returns 'ok', 'skip' or 'fail'.

    - Edits made on the GitHub website are pulled first
      (fast-forward only, when the local tree is clean and
      nothing local waits to be pushed).
    - Local changes are committed as "auto update: ..." and pushed.
    - A failed push must not lose the change: if the commit
      succeeded but the push failed, the next run still sees the
      commit as unpushed and retries the push.
    - Changed on both sides at once is not guessed at: it fails
      with a clear message and is left for the user to resolve.
    - A folder with no remote cannot be pushed anywhere: it fails
      with a clear message instead of a confusing push error.
    """
    name = path.name
    code, out, err = run(["git", "status", "--porcelain"], cwd=path)
    if code != 0:
        fail(f"{name}: could not check status. {last_line(err)}")
        return "fail"
    changed = [line for line in out.splitlines() if line.strip()]
    ahead, behind = sync_counts(path)
    if ahead is None and not has_remote(path):
        fail(f"{name}: has no remote on GitHub (no upstream). "
             f"Clone it again, or set the remote, then run again.")
        return "fail"
    if (behind or 0) > 0:
        if changed or (ahead or 0) > 0:
            fail(f"{name}: changed both here and on GitHub. "
                 f"Resolve it first, then run again.")
            return "fail"
        code, _out, err = run(["git", "pull", "--ff-only"], cwd=path)
        if code != 0:
            fail(f"{name}: could not pull updates from GitHub. {last_line(err)}")
            return "fail"
        ok(f"{name}: pulled {behind} update(s) from GitHub")
        return "ok"
    if not changed and (ahead or 0) == 0 and commit_count(path) == 0:
        # Nothing to push and nothing committed yet.
        skip(f"{name}: no changes")
        return "skip"
    committed = False
    if changed:
        code, _out, err = run(["git", "add", "-A"], cwd=path)
        if code != 0:
            fail(f"{name}: git add failed. {last_line(err)}")
            return "fail"
        # Nothing staged (for example only ignored files changed).
        code, _out, err = run(["git", "diff", "--cached", "--quiet"], cwd=path)
        if code != 0:
            message = f"auto update: {datetime.now():%Y-%m-%d %H:%M}"
            code, _out, err = run(["git", "commit", "-m", message], cwd=path)
            if code != 0:
                fail(f"{name}: git commit failed. {last_line(err)}")
                if "unable to auto-detect email address" in err:
                    # git has no name/email on this machine yet.
                    # Nothing is lost: the change is still there,
                    # and the next run retries the commit.
                    error("git does not know who you are. Run once:")
                    error('  git config --global user.name "Erffan_hub"')
                    error('  git config --global user.email '
                          '"erffanhub-00@users.noreply.github.com"')
                    error("Or use your own email instead of the "
                          "noreply address, then run again.")
                return "fail"
            committed = True
    if not committed and ahead == 0:
        skip(f"{name}: no changes")
        return "skip"
    if ahead is None:
        # A remote exists but no upstream is tracked (for example
        # a repo with no commits yet): push and set it.
        code, _out, err = run(["git", "push", "-u", "origin", "HEAD"], cwd=path)
    else:
        code, _out, err = run(["git", "push"], cwd=path)
    if code != 0:
        fail(f"{name}: git push failed. {last_line(err)}")
        return "fail"
    ok(f"{name}: pushed")
    return "ok"


__all__ = [
    "is_whitespace_only",
    "local_gist_map",
    "local_gists",
    "loose_files",
    "loose_folders",
    "sync_one",
]
