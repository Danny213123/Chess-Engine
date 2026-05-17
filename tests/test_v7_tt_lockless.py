"""V7 TT lockless probe/store unit tests — Wave 0 stub.

PAR-01/02: probe/store roundtrip + pack/unpack invariant.
Plan 03-05 implements the full lockless TT rewrite (D-07 Hyatt-Mann XOR)
and fills in these test bodies.

References: D-07 (Hyatt-Mann XOR, two atomic uint64_t slots per entry),
D-09 (bit-pack layout mirrors V6 verbatim), RESEARCH.md Pattern 1.
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


STARTPOS_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.mark.skip(reason="Plan 03-05 will implement; this is a Wave 0 stub")
def test_probe_store_roundtrip(v7_native_engine):
    """PAR-01: probe returns the same move/score/depth stored by store().

    After store(key, move, score, depth, TT_EXACT), probe(key) must return
    True and populate entry fields matching the stored values (within int16_t
    precision). Validates the Hyatt-Mann XOR pack/unpack cycle end-to-end.
    """
    pass


@pytest.mark.skip(reason="Plan 03-05 will implement; this is a Wave 0 stub")
def test_pack_unpack_invariant(v7_native_engine):
    """PAR-02: D-09 bit-pack invariant — all fields survive round-trip.

    Exercises all corner cases of the 64-bit layout:
      bits 0..15  → Move (uint16_t)
      bits 16..31 → score (int16_t)
      bits 32..39 → depth (int8_t)
      bits 40..47 → flag (uint8_t, 2 bits used)
      bits 48..55 → age (uint8_t)
    Per D-09: layout mirrors V6's TTEntry verbatim.
    """
    pass


@pytest.mark.skip(reason="Plan 03-05 will implement; this is a Wave 0 stub")
def test_replacement_age_then_depth(v7_native_engine):
    """D-07 replacement policy: age-then-depth.

    A new-generation entry must replace an old-generation entry regardless
    of depth. Within the same generation, higher depth must replace lower.
    (D-07: 'age-then-depth' policy; different from V6's OR-condition.)
    """
    pass
