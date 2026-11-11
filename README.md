# gist-sync

All your GitHub Gists, in one folder, kept in sync — with a menu you
drive with the arrow keys.

You choose one folder, once. Every gist lives in that folder, one
subfolder per gist. Edit a file in VS Code, open the menu, hit Auto
sync, and it is on GitHub. Edit a gist on the GitHub website instead,
and the next Auto sync pulls it down here. File names are never
renamed: files inside a gist keep exactly the name they have on
GitHub, or the name you gave the file when you created the gist.

## Quick start

```bash
# 1. Install gh and git, then log in once
sudo pacman -S github-cli git
gh auth login

# 2. Clone this repo and choose your gists folder
git clone https://github.com/erffanhub-00/gist-sync.git
cd gist-sync
python3 gist_sync.py setup

# 3. Open the menu
python3 gist_sync.py
```

No pip packages needed — standard library only. No token is stored
in this program; it uses your `gh` login. All terminal output is in
English. Python 3.9+.

## The menu

Running with no command opens the menu (`python3 gist_sync.py menu`
opens the same menu). Move with the **up/down arrow keys** and confirm
with **Enter** — the chosen line is highlighted. Typing the number
works too, and `q` quits. When arrow keys are not available, type the
number instead. The menu and status lines are colored on a terminal;
piped output stays plain.

```
  === gist-sync 1.8.0 ===
  > Auto sync
    Create new gist
    Delete a gist
    About Me
    Change gists folder
    Exit
  ↑ ↓ to move, Enter to choose, or type the number, q to quit
```

After each task it asks you to press Enter, then goes back to the
menu. Nothing runs by itself: Auto sync is only menu option 1 (or
`python3 gist_sync.py auto`).

## Auto sync

```bash
python3 gist_sync.py auto
```

Auto sync detects everything and asks once before changing anything:

- **Gists on GitHub missing locally** — cloned. You are asked for the
  folder name, with the program's suggestion shown as the default
  (Enter accepts it).
- **Files you changed locally** — listed by name, so you see exactly
  what really changed, never a vague count. Committed as
  `auto update: YYYY-MM-DD HH:MM` and pushed.
- **Commits waiting to be pushed** — listed as
  `2 commit(s) not pushed yet`, and pushed.
- **Edits you made on the GitHub website** — listed as
  `1 update(s) to pull from GitHub`, and pulled down (fast-forward
  only). If a gist changed both here and on the website at once, it
  is left alone with a clear message instead of being guessed at.
- **A file sitting directly in your gists folder** — offered as a new
  gist: public (1) or secret (2, default secret), description
  optional. After it is created, the loose file is removed, because
  it now lives inside its gist folder.
- **A folder sitting directly in your gists folder** — offered as one
  multi-file gist, the same way.

Before syncing, it asks `Show what changed?` (default No). Say yes
and it shows, per gist, the changed file names and a short diff
summary, plus the new commits waiting on GitHub — so you can check
where it changed before anything moves. Then it asks `Sync now?`
once (Enter means yes). If nothing changed, it just says
`Everything is up to date.` and does nothing on GitHub.

## Create a gist

Menu option 2, or:

```bash
# From a file (public by default)
python3 gist_sync.py create my-file.md --desc "My gist"

# Secret (unlisted) instead
python3 gist_sync.py create my-file.md --desc "My gist" --secret
```

From the menu you can also create from a **folder**: all its files
become one gist, so a Persian + English pair stays together. The
folder keeps the file's or folder's name — no name is asked, because
it already has one. The new gist is cloned into your gists folder
right after creation, so you can manage it like the others.

## Clone and folder names

```bash
python3 gist_sync.py clone
```

A gist created on the GitHub website still clones into a readable
folder: its name comes from the files inside it — one file gives its
name, several files give their common name part. There is no table
of gist ids to folder names anywhere in the program. A local gist is
recognised by the git remote of its folder, not by the folder's
name, so renaming a folder yourself changes nothing, and clone/auto
never make a duplicate copy under a different name.

## Lists and deleting

Lists show **10 items per page** (`list` and Delete): `n` goes to the
next page, `p` to the previous one, and numbering runs across pages.
When there is no terminal, a list is printed all at once.

Delete (menu option 3) fetches the freshest list from GitHub first,
shows only the name, and asks once more — No is the default — before
deleting the gist from GitHub and removing its local folder.

## All commands

| Command | What it does |
| --- | --- |
| `python3 gist_sync.py` | Open the menu (default) |
| `python3 gist_sync.py auto` | Detect everything, ask once, sync it all |
| `python3 gist_sync.py setup [folder]` | Choose the gists folder, once, saved |
| `python3 gist_sync.py list` | List all your gists on GitHub |
| `python3 gist_sync.py clone` | Clone all your gists into your folder |
| `python3 gist_sync.py status` | Show which local gists changed, are unpushed, or are behind GitHub |
| `python3 gist_sync.py sync` | Commit and push every changed gist; pull website edits |
| `python3 gist_sync.py create <file> [--secret] [--desc "..."]` | Create a new gist from file(s) |
| `python3 gist_sync.py menu` | Open the menu |

For a single run in another folder, without changing the saved
choice:

```bash
python3 gist_sync.py --base-dir ~/other-folder sync
```

## How sync works

For each folder in your chosen folder that is a git repo:

1. It fetches the latest state from GitHub first.
2. If the website has new commits and the local tree is clean, it
   pulls them (fast-forward only).
3. If files changed locally, they are committed as
   `auto update: YYYY-MM-DD HH:MM` and pushed.
4. If a push fails, the error is shown clearly, the other gists are
   still processed, and the failed gist is retried on the next run
   instead of being silently lost.

A summary is printed at the end. The program exits with code `1`
when any gist failed, so a timer or script can tell something went
wrong.

## Setup details

The chosen folder is saved in `~/.config/gist-sync/config.json`
(only the folder path, nothing secret). The default is `~/gists` —
just press Enter to accept it. Run `setup` again any time to change
the folder; files in the old folder stay where they are, the program
never moves them by itself.

## Frequently asked

**I edited a gist on the website. How do I get it here?**
Run Auto sync (menu option 1). It pulls the website's commits into
your local folder.

**I made a folder locally and put files in it. Can I upload it?**
Yes. Menu option 2 → From a folder. All its files become one gist,
the folder keeps its name, and the gist is cloned back into the same
folder, so you can keep editing it there.

**Can I rename a gist folder?**
Yes, rename it however you like. The program recognises a gist by
its git remote, not by its folder name.

**What if I have a lot of gists?**
Lists are paged 10 per page, and Delete always fetches the freshest
list from GitHub.

**`git commit failed: unable to auto-detect email address`?**
git on this machine does not know your name and email yet. Run
once, then run again — nothing is lost, the change is still there:

```bash
git config --global user.name "Erffan_hub"
git config --global user.email "erffanhub-00@users.noreply.github.com"
```

Or use your own email instead of the noreply address. (Your exact
noreply address is in GitHub Settings → Emails.)

**A file shows many insertions and deletions, but I barely changed it?**
That is usually a line-ending change (the whole file rewritten with
LF instead of CRLF, or the other way round). Auto sync labels it
`(line endings/whitespace only)` — the content is the same.

**Something failed. Did I lose my change?**
No. A failed push leaves the commit unpushed, and the next run
retries it. A failed pull leaves your local files untouched.

## Me

[![Telegram](https://img.shields.io/badge/Telegram-erffan__hub-blue?style=for-the-badge&logo=telegram)](https://t.me/erffan_hub)
[![Twitter](https://img.shields.io/badge/Twitter-@Erffanhub__00-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/Erffanhub_00)
[![Gist](https://img.shields.io/badge/Gist-Profile-000000?style=for-the-badge&logo=github)](https://gist.github.com/erffanhub-00)
[![Github](https://img.shields.io/badge/Github-Profile-000000?style=for-the-badge&logo=github)](https://github.com/erffanhub-00)
