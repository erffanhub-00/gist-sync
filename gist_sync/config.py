"""Where the gists live: one folder, chosen once with `setup`.

The choice is saved in ~/.config/gist-sync/config.json (only the
folder path, nothing secret). `--base-dir` overrides it for a
single run without changing the saved choice.
"""

import json
import os
import sys
from pathlib import Path

from .output import error, info

USERNAME = "erffanhub-00"
DEFAULT_BASE = Path.home() / "gists"
CONFIG_PATH = Path.home() / ".config" / "gist-sync" / "config.json"


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
    """Ask the user to choose the gists folder. Returns a Path.

    Pressing Enter accepts the default ~/gists. When there is no
    terminal to ask in (for example a script), the default is used
    without asking, so the program never hangs waiting for input.
    """
    if not sys.stdin.isatty():
        return DEFAULT_BASE
    print("Your gists will live in one folder. Each gist is one subfolder.")
    try:
        answer = input(
            f"Which folder should hold all your gists? [{DEFAULT_BASE}] "
        ).strip()
    except EOFError:
        return DEFAULT_BASE
    if not answer:
        return DEFAULT_BASE
    return expand_folder(answer)


def resolve_base_dir(args):
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
    base = prompt_for_folder()
    if not validate_folder(base):
        return None
    # Only save a fresh choice. A broken config file is left alone
    # so setup can fix it, instead of silently overwriting it.
    if not had_config_file and save_config(base):
        info(f"Saved your gists folder: {base}")
    return base
