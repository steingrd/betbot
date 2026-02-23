#!/usr/bin/env python3
"""Entry point for BetBot TUI dashboard."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tui.app import BetBotApp


def main():
    app = BetBotApp()
    app.run()


if __name__ == "__main__":
    main()
