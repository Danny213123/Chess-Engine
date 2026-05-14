"""Compatibility shim for the historical ``main`` package."""

from __future__ import annotations

import importlib
import sys

for _name in ("engine", "server"):
    sys.modules[f"{__name__}.{_name}"] = importlib.import_module(f"chess_engine.{_name}")

from chess_engine import *  # noqa: F401,F403,E402
