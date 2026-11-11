# gist-sync

Manage all your GitHub Gists from one folder, with clean error handling.

You choose one folder, once. All your gists live in that folder, one
subfolder per gist. Edit a gist file in VS Code, run one command, and
it is pushed to GitHub. File names are never renamed: files inside a
gist keep exactly the name they have on GitHub, or the name you gave
the file when you created the gist.

## Requirements

- Python 3.9+
- `git` and `gh` (GitHub CLI), logged in with `gh auth login`

```bash
sudo pacman -S github-cli git
gh auth login
```

No pip packages needed. Standard library only. No token is stored in
this program; it uses your `gh` login. All terminal output is in
English.

## Setup: choose your folder

```bash
# Ask once, save the choice, and use it from then on
python3 gist_sync.py setup

# Or give the folder directly
python3 gist_sync.py setup ~/my-gists
```

The choice is saved in `~/.config/gist-sync/config.json` (only the
folder path, nothing secret). The default is `~/gists` — just press
Enter to accept it. Run `setup` again any time to change the folder.
Files in the old folder stay where they are; the program never moves
them by itself.

For a single run only, without changing the saved choice:

```bash
python3 gist_sync.py --base-dir ~/other-folder sync
```

## Usage

Just run it with no command. It detects everything by itself:

```bash
python3 gist_sync.py
```

It finds what changed, what is new, what was deleted, and which
gists are missing locally, shows one short summary, asks once
(`Sync now? [Y/n]` — Enter means yes), and does it all. A file
sitting directly in your gists folder (not inside a subfolder) is
offered as a new gist: it asks public (1) or secret (2), then
creates it, clones it into its own folder, and removes the loose
file, because it now lives inside its gist folder. If nothing
changed, it just says `Everything is up to date.` and does
nothing on GitHub.

The old commands still work, when you want one specific thing:

```bash
# See all your gists on GitHub
python3 gist_sync.py list

# Clone all your gists into your chosen folder (friendly folder names, files unchanged)
python3 gist_sync.py clone

# Show which local gists have unpushed changes
python3 gist_sync.py status

# Commit and push every changed gist in your chosen folder
python3 gist_sync.py sync

# Create a new gist from a file (public by default)
python3 gist_sync.py create my-file.md --desc "My gist"

# Create a secret (unlisted) gist instead
python3 gist_sync.py create my-file.md --desc "My gist" --secret
```

A new gist is cloned into your chosen folder automatically after
creation, in a folder named after the file you gave it, so you can
manage it like the others from then on.

## How sync works

For each folder in your chosen folder that is a git repo:

1. If nothing changed, it is skipped.
2. If files changed, they are committed as `auto update: YYYY-MM-DD HH:MM`.
3. The commit is pushed.
4. If the push fails, the error is shown clearly, the other gists are
   still processed, and the failed gist is retried on the next run
   instead of being silently lost.

A summary is printed at the end: how many were pushed, skipped, and
failed. The program exits with code `1` when any gist failed, so a
timer or script can tell something went wrong.

## Me

[![Telegram](https://img.shields.io/badge/Telegram-erffan__hub-blue?style=for-the-badge&logo=telegram)](https://t.me/erffan_hub)
[![Twitter](https://img.shields.io/badge/Twitter-@Erffanhub__00-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/Erffanhub_00)
[![Gist](https://img.shields.io/badge/Gist-Profile-000000?style=for-the-badge&logo=github)](https://gist.github.com/erffanhub-00)
[![Github](https://img.shields.io/badge/Github-Profile-000000?style=for-the-badge&logo=github)](https://github.com/erffanhub-00)
