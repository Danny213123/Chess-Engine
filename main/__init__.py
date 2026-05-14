"""Compatibility shim for the historical ``main`` package."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_PACKAGE = importlib.import_module("chess_engine")
_SUBPACKAGES = ("engine", "server")

for _name in _SUBPACKAGES:
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(f"chess_engine.{_name}")

from chess_engine import *  # noqa: F401,F403,E402
