"""Compatibility shim for historical ``engine`` imports."""

from __future__ import annotations

import importlib

_ENGINE = importlib.import_module("chess_engine.engine")
__path__ = _ENGINE.__path__

from chess_engine.engine import *  # noqa: F401,F403,E402
