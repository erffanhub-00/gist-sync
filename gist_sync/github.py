"""Talking to GitHub through the `gh` CLI. No token is stored here."""

import json
import os
import shutil
from pathlib import Path

from .config import USERNAME
from .gitutil import last_line, run
from .output import error

# The API returns this many gists per page; fetch_gists walks
# through the pages, so having more gists than this still works.
GISTS_PER_PAGE = 100


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


def _parse_gist_items(data):
    """Turn one page of API/list JSON into gist dicts, or None."""
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


def _parse_page(out):
    """Parse one page of JSON, or None when it cannot be read."""
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        error("GitHub returned a response this program could not read.")
        return None
    return _parse_gist_items(data)


def fetch_gists():
    """Return a list of {'id', 'description', 'files'}, or None on error.

    Pages through the API, so all gists are returned even when
    there are more than one page of them. 'files' is the list of
    file names inside the gist, as GitHub reports them. It is used
    to name the local folder when cloning.
    """
    gists = []
    page = 1
    while True:
        code, out, err = run(
            ["gh", "api",
             f"users/{USERNAME}/gists?per_page={GISTS_PER_PAGE}&page={page}"]
        )
        if code != 0:
            if page > 1:
                error("Could not fetch your gists from GitHub.")
                if err.strip():
                    error(last_line(err))
                return None
            break  # First page failed: try the fallback below.
        items = _parse_page(out)
        if items is None:
            return None
        gists.extend(items)
        if len(items) < GISTS_PER_PAGE:
            return gists
        page += 1

    # Fallback for the first page: gh gist list with JSON output.
    code, out, err = run(
        ["gh", "gist", "list", "--limit", "1000",
         "--json", "id,description,files"]
    )
    if code != 0:
        error("Could not fetch your gists from GitHub.")
        if err.strip():
            error(last_line(err))
        else:
            error("Check your internet connection and run: gh auth status")
        return None
    return _parse_page(out)


def folder_name_for_gist(gist):
    """Folder name for a gist dict from fetch_gists.

    The name comes from the files inside the gist: one file ->
    its name without the extension (my-guide.md -> my-guide);
    several files -> their common name part (guide-fa + guide-en
    -> guide). So a gist created on the GitHub website still
    clones into a readable folder instead of its 32-character
    id. Otherwise (no files listed) the gist id itself.
    """
    stems = [Path(name).stem for name in (gist.get("files") or []) if name]
    if not stems:
        return gist["id"]
    if len(stems) == 1:
        return stems[0]
    prefix = os.path.commonprefix(stems).rstrip("-_.")
    if len(prefix) >= 3:
        return prefix
    return stems[0]
