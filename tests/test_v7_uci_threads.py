"""V7 UCI Threads option contract tests — PAR-04 (Plan 04-01).

Wave 0 scaffolding: tests are EXPECTED TO FAIL / ERROR until Task 2 lands
the EngineOptions.Threads field, Engine::set_option Threads case, and
ThreadPool pool_.resize() wiring.

Test plan:
  1. test_threads_option_exists    — Threads option is declared in UCI handshake
  2. test_set_option_threads_valid — valid int in [1,256] accepted and stored
  3. test_set_option_threads_zero_rejected  — 0 rejected, Threads unchanged
  4. test_set_option_threads_too_high_rejected — 257 rejected, Threads unchanged
  5. test_set_option_threads_non_integer_rejected — non-int rejected, info string

References: PAR-04 / T-04-01 (REQUIREMENTS.md + STRIDE threat register);
CONTEXT D-04 (min 1, max 256, default 1); PATTERNS §engine.cpp set_option pattern.
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


# =============================================================================
# Shared Pattern 2 (CANONICAL) — module-scoped V7 native-engine fixture
# Source: tests/test_v7_tt_lockless.py:34-50 (verbatim copy target)
# =============================================================================

@pytest.fixture(scope="module")
def v7_native_engine():
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.fixture()
def engine(v7_native_engine):
    """Fresh Engine per test — TT cleared, options at defaults."""
    eng = v7_native_engine.Engine()
    eng.tt_clear()
    return eng


# =============================================================================
# Test 1 — Threads option is declared in the UCI 'uci' handshake
# =============================================================================

def test_threads_option_exists(v7_native_engine):
    """PAR-04: 'option name Threads type spin default 1 min 1 max 256' must be
    declared in uci_main.cpp and surfaced via the UCI protocol.

    This test verifies the static acceptance criterion from 04-01-PLAN.md:
      grep -c 'option name Threads type spin default 1 min 1 max 256' uci_main.cpp

    Wave 0: grep is the structural check; the test passes ONLY if the string is
    in the file. If Task 2 hasn't added it yet this test fails.
    """
    import subprocess
    import sys
    from pathlib import Path

    # Find uci_main.cpp relative to the repo root
    repo_root = Path(__file__).parent.parent
    uci_main = repo_root / "src" / "chess_engine" / "engine" / "v7" / "src" / "uci_main.cpp"

    if not uci_main.exists():
        pytest.skip(f"uci_main.cpp not found at {uci_main}")

    needle = "option name Threads type spin default 1 min 1 max 256"
    text = uci_main.read_text(encoding="utf-8")
    assert needle in text, (
        f"'{needle}' not found in uci_main.cpp — "
        "Task 2(e) must add it (alphabetical between UseSingular and uciok)"
    )


# =============================================================================
# Test 2 — set_option("Threads", "4") stores and thread_count() reflects it
# =============================================================================

def test_set_option_threads_valid(engine):
    """PAR-04: valid Threads value in [1, 256] is stored in EngineOptions.Threads.

    Wave 0: engine.thread_count() accessor does not exist yet — FAIL expected.
    """
    engine.set_option("Threads", "4")
    assert engine.thread_count() == 4, (
        "thread_count() must return 4 after set_option(Threads, '4')"
    )
    engine.set_option("Threads", "1")
    assert engine.thread_count() == 1, (
        "thread_count() must return 1 after set_option(Threads, '1')"
    )
    engine.set_option("Threads", "256")
    assert engine.thread_count() == 256, (
        "thread_count() must accept max value 256"
    )
    engine.set_option("Threads", "1")  # reset


# =============================================================================
# Test 3 — Threads=0 is rejected; previous value stays unchanged
# =============================================================================

def test_set_option_threads_zero_rejected(engine, capsys):
    """T-04-01: Threads=0 is below min=1; must leave Threads unchanged + emit info string."""
    engine.set_option("Threads", "4")   # set a known baseline
    assert engine.thread_count() == 4

    engine.set_option("Threads", "0")
    out = capsys.readouterr().out
    assert engine.thread_count() == 4, (
        "Threads=0 must leave Threads unchanged (out of range [1,256])"
    )
    assert "info string" in out, (
        "Threads=0 rejection must emit 'info string ...' per UCI convention"
    )
    engine.set_option("Threads", "1")  # reset


# =============================================================================
# Test 4 — Threads=257 is rejected (above max); previous value stays
# =============================================================================

def test_set_option_threads_too_high_rejected(engine, capsys):
    """T-04-01: Threads=257 is above max=256; must leave Threads unchanged + emit info string."""
    engine.set_option("Threads", "4")   # set a known baseline
    assert engine.thread_count() == 4

    engine.set_option("Threads", "257")
    out = capsys.readouterr().out
    assert engine.thread_count() == 4, (
        "Threads=257 must leave Threads unchanged (out of range [1,256])"
    )
    assert "info string" in out, (
        "Threads=257 rejection must emit 'info string ...' per UCI convention"
    )
    engine.set_option("Threads", "1")  # reset


# =============================================================================
# Test 5 — non-integer Threads is rejected; previous value stays + info string
# =============================================================================

def test_set_option_threads_non_integer_rejected(engine, capsys):
    """T-04-01: non-integer Threads value must leave Threads unchanged and emit info string."""
    engine.set_option("Threads", "4")   # set a known baseline
    assert engine.thread_count() == 4

    engine.set_option("Threads", "not-an-int")
    out = capsys.readouterr().out
    assert engine.thread_count() == 4, (
        "non-integer Threads must leave Threads unchanged"
    )
    assert "info string" in out, (
        "non-integer rejection must emit 'info string ...' per UCI convention"
    )
    engine.set_option("Threads", "1")  # reset
