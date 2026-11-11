"""The commands: setup, list, clone, status, sync, create, auto."""

import shutil
from pathlib import Path

from .config import (
    USERNAME,
    expand_folder,
    load_config,
    prompt_for_folder,
    resolve_base_dir,
    save_config,
    validate_folder,
)
from .github import check_gh, check_git, fetch_gists, folder_name_for_gist
from .gitutil import commit_count, is_whitespace_only, last_line, run, sync_counts
from .local import local_gist_map, local_gists, loose_files, loose_folders, sync_one
from .output import error, fail, info, ok, skip
from .ui import (
    ask_description,
    ask_folder_name,
    ask_public_or_secret,
    ask_yes_no,
    pick_from_list,
)


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
    if not validate_folder(base):
        return 1
    if not save_config(base):
        return 1
    ok(f"Gists folder set to: {base}")
    info("All your gists will live in that folder.")
    return 0


def cmd_list(args):
    """List all your gists on GitHub.

    Shows only the name and the files inside, never the
    description: descriptions can be Persian, and Persian does
    not display correctly in the terminal.
    """
    if not check_gh():
        return 1
    gists = fetch_gists()
    if gists is None:
        return 1
    if not gists:
        info("No gists found.")
        return 0
    pick_from_list(
        gists,
        lambda gist: folder_name_for_gist(gist)
        + (f" ({', '.join(gist['files'])})" if gist["files"] else ""),
        title=f"Gists for {USERNAME} ({len(gists)}):",
        allow_pick=False,
    )
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
    present = local_gist_map(base)
    cloned = skipped = failed = 0
    for gist in gists:
        if gist["id"] in present:
            skip(f"{present[gist['id']].name}: already exists")
            skipped += 1
            continue
        name = folder_name_for_gist(gist)
        target = base / ask_folder_name(name, label=f"Folder name for {name}")
        if target.is_dir():
            if (target / ".git").is_dir():
                skip(f"{target.name}: already exists")
                skipped += 1
            else:
                fail(f"{target.name}: folder exists but is not a git repo")
                failed += 1
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
        ahead, behind = sync_counts(path)
        # Commits with no upstream are unpushed, not clean.
        unpushed_no_upstream = ahead is None and commit_count(path) > 0
        if (not changed and (ahead or 0) == 0 and (behind or 0) == 0
                and not unpushed_no_upstream):
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
                count = commit_count(path)
                if count > 0:
                    print(f"[UNPUSHED] {path.name}: {count} commit(s) "
                          f"not pushed yet (no upstream)")
                else:
                    print(f"[UNPUSHED] {path.name}: no upstream to compare")
            elif ahead > 0:
                print(f"[UNPUSHED] {path.name}: {ahead} commit(s) not pushed yet")
            if (behind or 0) > 0:
                print(f"[BEHIND] {path.name}: {behind} commit(s) on GitHub, "
                      f"run sync to pull them")
    return 0


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


def _move_back(moved_aside, source_folder):
    """Move a folder back after a failed create/clone. Best effort."""
    try:
        moved_aside.rename(source_folder)
    except OSError:
        pass


def create_gist_and_clone(files, secret, desc, base, target_name=None,
                          source_folder=None):
    """Create a gist from files, then clone it into base.

    The folder is named after the first file (stem), or
    target_name when given (the source folder's name when the
    files came from a folder). No name is asked here: the file
    or folder already exists and already has a name. Asking for
    a folder name only happens when cloning a gist from GitHub.
    Returns 0 on success.

    When the files came from a folder inside base (source_folder),
    that folder is moved aside BEFORE anything is created on
    GitHub, then removed after a successful clone: the cloned
    folder keeps the source folder's name, with the same files
    inside. The files are read from their new place, so `gh`
    still sees them. If creating or cloning fails, the source
    folder is moved back, so nothing is lost.
    """
    folder = target_name or Path(files[0]).stem
    target = base / folder if folder else base
    moved_aside = None
    if source_folder is not None and target == source_folder:
        # Move aside first: a problem here must fail before the
        # gist exists on GitHub, not after. gh reads the files
        # from their new place below.
        moved_aside = base / (".gist-sync-tmp-" + folder)
        if moved_aside.exists():
            # Left over from an interrupted earlier run: ours to remove.
            shutil.rmtree(moved_aside, ignore_errors=True)
        try:
            source_folder.rename(moved_aside)
        except OSError as exc:
            error(f"Could not move the folder aside: {exc}")
            return 1
        files = [moved_aside / Path(p).name for p in files]
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
        if moved_aside is not None:
            _move_back(moved_aside, source_folder)
        return 1
    url = out.strip().splitlines()[-1].strip() if out.strip() else ""
    gist_id = url.rstrip("/").split("/")[-1] if url else ""
    ok(f"Created gist: {url or '(no URL returned)'}")
    if not gist_id:
        info("Run: python3 gist_sync.py clone  to fetch it locally.")
        if moved_aside is not None:
            _move_back(moved_aside, source_folder)
        return 0
    if not folder:
        folder = gist_id
        target = base / folder
    if target.is_dir():
        # A folder with that name already exists (not the source
        # folder, which was moved aside): use the gist id instead
        # of overwriting it.
        target = base / gist_id
    if target.is_dir():
        info(f"Local folder already exists: {target}")
        if moved_aside is not None:
            _move_back(moved_aside, source_folder)
        return 0
    code, _out, err = run(["gh", "gist", "clone", gist_id, str(target)])
    if code != 0:
        fail(f"Created on GitHub, but clone failed. {last_line(err)}")
        info("Run: python3 gist_sync.py clone  to fetch it locally.")
        if moved_aside is not None:
            _move_back(moved_aside, source_folder)
        return 1
    if moved_aside is not None:
        shutil.rmtree(moved_aside, ignore_errors=True)
    ok(f"Cloned locally to: {target}")
    return 0


def cmd_auto(args):
    """Auto mode: detect everything, ask once, do it all.

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

    # What is missing locally? A gist is present when a local
    # folder's git remote points at it, whatever the folder is
    # called (see local_gist_map).
    present = local_gist_map(base)
    missing = [gist for gist in gists if gist["id"] not in present]

    # What changed locally? Only real changes are listed: the
    # file names that actually changed, commits waiting to be
    # pushed, and updates waiting to be pulled from GitHub.
    # Each entry says exactly which one it is, so "0 file(s)
    # changed" never shows up.
    changed = []
    for path in local_gists(base):
        code, out, err = run(["git", "status", "--porcelain"], cwd=path)
        if code != 0:
            fail(f"{path.name}: could not check status. {last_line(err)}")
            continue
        lines = [line for line in out.splitlines() if line.strip()]
        ahead, behind = sync_counts(path)
        if lines or (ahead is None) or (ahead or 0) > 0 or (behind or 0) > 0:
            changed.append(
                {"path": path, "lines": lines,
                 "ahead": ahead, "behind": behind,
                 "ws_only": bool(lines) and is_whitespace_only(path, lines)}
            )

    loose = loose_files(base)
    folders = loose_folders(base)

    if not missing and not changed and not loose and not folders:
        ok("Everything is up to date.")
        return 0

    print("Found:")
    for gist in missing:
        print(f"  {folder_name_for_gist(gist)}: missing locally, will be cloned")
    for item in changed:
        parts = []
        if item["lines"]:
            names = [line[3:].strip() for line in item["lines"]]
            shown = ", ".join(names[:5])
            if len(names) > 5:
                shown += f", ... and {len(names) - 5} more"
            label = f"{len(names)} file(s) changed: {shown}"
            if item["ws_only"]:
                label += " (line endings/whitespace only)"
            parts.append(label)
        if (item["ahead"] or 0) > 0:
            parts.append(f"{item['ahead']} commit(s) not pushed yet")
        if item["ahead"] is None:
            parts.append("no upstream to compare")
        if (item["behind"] or 0) > 0:
            parts.append(f"{item['behind']} update(s) to pull from GitHub")
        print(f"  {item['path'].name}: {'; '.join(parts)}")
    for path in loose:
        print(f"  {path.name}: new file, not in any gist yet")
    for path, files in folders:
        print(f"  {path.name}/: new folder with {len(files)} file(s), "
              f"not a gist yet")

    if changed and ask_yes_no("Show what changed?", default=False):
        for item in changed:
            path = item["path"]
            if not item["lines"] and not (item["behind"] or 0) > 0:
                continue
            print(f"--- {path.name} ---")
            for line in item["lines"][:10]:
                print(f"    {line.strip()}")
            if len(item["lines"]) > 10:
                print(f"    ... and {len(item['lines']) - 10} more")
            code, out, _err = run(["git", "diff", "--stat"], cwd=path)
            if code == 0 and out.strip():
                print(out.rstrip())
            if item["ws_only"]:
                print("  (Only line endings/whitespace changed — "
                      "the content is the same.)")
            if (item["behind"] or 0) > 0:
                code, out, _err = run(
                    ["git", "log", "--oneline", "HEAD..@{u}"], cwd=path
                )
                if code == 0 and out.strip():
                    print("  New on GitHub:")
                    for line in out.splitlines():
                        print(f"    {line.strip()}")

    if not ask_yes_no("Sync now?", default=True):
        info("Nothing changed on GitHub.")
        return 0

    failed = 0
    for gist in missing:
        name = folder_name_for_gist(gist)
        target = base / ask_folder_name(name, label=f"Folder name for {name}")
        info(f"Cloning {target.name} ({gist['id']}) ...")
        code, _out, err = run(["gh", "gist", "clone", gist["id"], str(target)])
        if code != 0:
            fail(f"{target.name}: clone failed. {last_line(err)}")
            failed += 1
        else:
            ok(f"{target.name}: cloned")
    for item in changed:
        if sync_one(item["path"]) == "fail":
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
