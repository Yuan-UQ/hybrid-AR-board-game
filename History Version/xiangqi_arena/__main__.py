"""
Allows the package to be executed as a module:
    python -m xiangqi_arena

This repository contains two implementations:

- `xiangqi_arena/` (legacy UI)
- `hybrid-AR-board-game-Frontend/xiangqi_arena/` (animated UI + ArtResource)

To preserve the team's animated UI, this entrypoint will prefer the Frontend
implementation when present.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _exec_frontend_if_present() -> bool:
    """
    Prefer the animated Frontend implementation when present.

    We `exec` a new Python process instead of importing the module in-process
    to avoid name collisions between the two `xiangqi_arena` packages.
    """
    repo_root = Path(__file__).resolve().parents[1]
    frontend_main = repo_root / "hybrid-AR-board-game-Frontend" / "xiangqi_arena" / "main.py"
    if not frontend_main.exists():
        return False

    os.execv(sys.executable, [sys.executable, str(frontend_main)])
    return True  # unreachable


if not _exec_frontend_if_present():
    from xiangqi_arena.main import main

    main()
