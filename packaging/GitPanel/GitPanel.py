#!/usr/bin/env python3
"""git-iterm2 — source control panel in the iTerm2 toolbelt."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_iterm2.panel import main  # noqa: E402

main()
