#!/usr/bin/env python3
"""Entry point for BetBot TUI dashboard."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.tui.app import BetBotApp


def main():
    app = BetBotApp()
    app.run()


if __name__ == "__main__":
    main()
