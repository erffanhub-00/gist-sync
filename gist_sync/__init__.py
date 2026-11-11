"""gist-sync: manage all your GitHub Gists from one folder.

One module per job, so each part can be read and tested on its own:

- output: terminal output (colors only on a terminal, English only)
- config: where the gists live (saved choice, --base-dir, setup)
- gitutil: running git and reading its answers
- github: talking to GitHub through the `gh` CLI
- local: the gist folders on this machine, and syncing one of them
- ui: asking the user things (menus, prompts, lists)
- commands: the commands (list, clone, status, sync, create, auto)
- menu: the arrow-key menu (what runs with no command)
- cli: argument parsing and the entry point
"""

__version__ = "1.9.0"
