"""Позволяет запускать пакет как `python -m md_slides`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
