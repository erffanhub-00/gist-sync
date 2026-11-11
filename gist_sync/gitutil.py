"""Small git helpers. Nothing here prints; callers report errors."""

import subprocess


def run(cmd, cwd=None, timeout=120):
    """Run a command. Never raises for a missing command or timeout.

    Returns (returncode, stdout, stderr). returncode -1 means the
    command could not be started at all. Output is decoded with
    errors replaced, so an unexpected byte never crashes the run.
    """
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            errors="replace", timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", "command timed out"
    except OSError as exc:
        return -1, "", str(exc)


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


def has_remote(path):
    """True when the repo has a remote called origin."""
    code, out, _err = run(
        ["git", "config", "--get", "remote.origin.url"], cwd=path
    )
    return code == 0 and bool(out.strip())


def commit_count(path):
    """Number of commits on HEAD, or 0 when there is no commit yet."""
    code, out, _err = run(["git", "rev-list", "--count", "HEAD"], cwd=path)
    if code != 0:
        return 0
    try:
        return int(out.strip())
    except ValueError:
        return 0


def sync_counts(path):
    """Return (ahead, behind) vs the upstream, or (None, None).

    ahead = local commits not pushed yet; behind = commits on
    GitHub not pulled yet. Runs `git fetch` first, so the
    comparison uses the latest state from GitHub. (None, None)
    means there is no upstream to compare with (for example a
    repo with no remote yet, or no commits yet). A failed fetch
    (offline?) is not fatal: the last fetched state is used instead.
    """
    run(["git", "fetch", "--quiet"], cwd=path)
    code, out, _err = run(
        ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"],
        cwd=path,
    )
    if code != 0:
        return None, None
    try:
        ahead, behind = (int(n) for n in out.split())
        return ahead, behind
    except ValueError:
        return None, None


def is_whitespace_only(path, lines):
    """True when the change is only whitespace / line endings.

    A new (untracked) file is always a real change, so any '??'
    line means False. Otherwise `git diff HEAD --ignore-all-space`
    says whether anything but whitespace changed. Compared against
    HEAD (not the index), so changes staged by an earlier failed
    run are counted too.
    """
    for line in lines:
        if line.startswith("??"):
            return False
    code, _out, _err = run(
        ["git", "diff", "HEAD", "--quiet", "--ignore-all-space"], cwd=path
    )
    return code == 0
