"""Compatibility shim for historical ``engine`` imports."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_ENGINE = importlib.import_module("chess_engine.engine")
__path__ = _ENGINE.__path__

from chess_engine.engine import *  # noqa: F401,F403,E402
