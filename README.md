# gist-sync

Manage all your GitHub Gists from one folder, with clean error handling.

One folder (`~/gists`) plus one Python program (`gist_sync.py`). Edit a gist
file in VS Code, run one command, and it is pushed to GitHub. File names
are never renamed: files inside a gist keep exactly the name they have
on GitHub, or the name you gave the file when you created the gist.

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

## Usage

```bash
# See all your gists on GitHub
python3 gist_sync.py list

# Clone all your gists into ~/gists (friendly folder names, files unchanged)
python3 gist_sync.py clone

# Show which local gists have unpushed changes
python3 gist_sync.py status

# Commit and push every changed gist in ~/gists
python3 gist_sync.py sync

# Create a new gist from a file (public by default)
python3 gist_sync.py create my-file.md --desc "My gist"

# Create a secret (unlisted) gist instead
python3 gist_sync.py create my-file.md --desc "My gist" --secret
```

A new gist is cloned into `~/gists` automatically after creation, in a
folder named after the file you gave it, so you can manage it like the
others from then on.

## How sync works

For each folder in `~/gists` that is a git repo:

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
