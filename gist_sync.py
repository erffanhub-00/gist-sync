#!/usr/bin/env python3
"""Entry point: python3 gist_sync.py

The real code lives in the gist_sync package next to this file,
one module per job (output, config, gitutil, github, local, ui,
commands, menu, cli). This file only starts it, so the way you
run it never changes. You can also run: python3 -m gist_sync
"""

import sys

from gist_sync.cli import main

if __name__ == "__main__":
    sys.exit(main())
