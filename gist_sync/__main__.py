"""Run the program as a module: python3 -m gist_sync."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
