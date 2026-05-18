"""V7 lockless TT — probe/store + age-then-depth replacement (Plan 03-05).

Implements PAR-01 (Hyatt-Mann XOR validation) and PAR-02 (memory_order_relaxed
atomics) acceptance via the Engine.tt_* test surface bound in
src/chess_engine/engine/v7/src/python_bindings.cpp.

Test plan (matches <behavior> block in 03-05-PLAN.md):
  1. test_probe_after_store_returns_same_entry — round-trip a single entry
  2. test_probe_unknown_hash_returns_false      — miss accounting on empty slot
  3. test_same_key_always_replaces              — D-07 same-key refresh
  4. test_different_age_replaces_same_age_at_lower_depth — D-07 age-then-depth
  5. test_same_age_depth_tie_break              — D-07 depth tie-break (no replace)
  6. test_clear_zeroes_table                    — clear() invariant + counter reset

References: D-07 (Hyatt-Mann XOR, age-then-depth), D-09 (V6 bit-pack layout),
RESEARCH.md Pattern 1, PATTERNS.md Shared Pattern 8 (score_to_tt stays on
SEARCH side — these tests do not exercise mate-distance correction).
"""

from __future__ import annotations

import pytest

from chess_engine.engine.v7 import chess_algorithm as v7


# TT flag constants (mirror v7::TTFlag enum in include/tt.hpp:14-18).
TT_NONE = 0
TT_EXACT = 1
TT_ALPHA = 2
TT_BETA = 3


@pytest.fixture(scope="module")
def v7_native_engine():
    """Auto-build V7 on first use, skip the module if the build fails."""
    try:
        return v7.ensure_available(auto_build=True)
    except v7.V7UnavailableError as error:
        pytest.skip(f"V7 native engine unavailable: {error}")
    except Exception as error:  # noqa: BLE001 — pytest.skip is the contract
        pytest.skip(f"V7 native engine unavailable: {error}")


@pytest.fixture()
def engine(v7_native_engine):
    """Fresh Engine per test: clear TT + reset generation."""
    eng = v7_native_engine.Engine()
    eng.tt_clear()
    return eng


# ---------------------------------------------------------------------------
# Test 1 — single round-trip: probe-after-store recovers all fields.
# ---------------------------------------------------------------------------
def test_probe_after_store_returns_same_entry(engine):
    """PAR-01: store then probe returns the same move/score/depth/flag."""
    h = 0xDEADBEEFCAFEBABE
    move = 0x1234       # uint16_t move encoding (arbitrary)
    score = -42         # negative int16_t to exercise sign-extension
    depth = 7
    flag = TT_EXACT

    engine.tt_store(h, move, score, depth, flag)
    hit, m_out, s_out, d_out, f_out, _age = engine.tt_probe(h)

    assert hit is True
    assert m_out == move
    assert s_out == score
    assert d_out == depth
    assert f_out == flag


# ---------------------------------------------------------------------------
# Test 2 — probe on empty (cleared) TT misses; miss counter bumps.
# ---------------------------------------------------------------------------
def test_probe_unknown_hash_returns_false(engine):
    """Fresh TT: probe(any) returns False; miss_count increments."""
    misses_before = engine.tt_misses()
    hit, *_ = engine.tt_probe(0xAAAA_BBBB_CCCC_DDDD)
    assert hit is False
    assert engine.tt_misses() == misses_before + 1


# ---------------------------------------------------------------------------
# Test 3 — same key always replaces (D-07 refresh contract).
# ---------------------------------------------------------------------------
def test_same_key_always_replaces(engine):
    """D-07: same-key store ALWAYS replaces, even when new depth < old depth."""
    h = 0x1111_2222_3333_4444
    engine.tt_store(h, best_move=0xAAAA, score=100, depth=10, flag=TT_EXACT)
    engine.tt_store(h, best_move=0xBBBB, score=-50, depth=5,  flag=TT_ALPHA)

    hit, m_out, s_out, d_out, f_out, _age = engine.tt_probe(h)
    assert hit is True
    # The SECOND store wins — same-key refresh regardless of depth.
    assert m_out == 0xBBBB
    assert s_out == -50
    assert d_out == 5
    assert f_out == TT_ALPHA


# ---------------------------------------------------------------------------
# Test 4 — different age beats same age even at lower depth (D-07).
# ---------------------------------------------------------------------------
def test_different_age_replaces_same_age_even_at_lower_depth(engine):
    """D-07: stale-generation entry MUST be replaced even by a shallower depth.

    Construct two hashes that map to the same slot (h2 = num_entries → both
    hash to index 0). Store at generation 0 with depth 20; advance generation;
    store the collider at depth 5. Probe(h2) must succeed — the older deeper
    entry was evicted because it was stale.
    """
    n = engine.tt_num_entries()
    assert n > 0
    h1 = 0
    h2 = n  # h2 % n == 0, so h1 and h2 collide on slot 0.
    assert h1 != h2

    engine.tt_store(h1, best_move=0xAAAA, score=100, depth=20, flag=TT_EXACT)
    engine.tt_new_search()  # generation_++
    engine.tt_store(h2, best_move=0xBBBB, score=200, depth=5,  flag=TT_BETA)

    hit, m_out, s_out, d_out, f_out, _age = engine.tt_probe(h2)
    assert hit is True
    # h2's entry overwrote h1's even though new depth (5) < old depth (20),
    # because h1's age was stale.
    assert m_out == 0xBBBB
    assert s_out == 200
    assert d_out == 5
    assert f_out == TT_BETA

    # And h1 is gone — probe(h1) now misses because the XOR validator fails
    # against the data packed under h2.
    hit_h1, *_ = engine.tt_probe(h1)
    assert hit_h1 is False


# ---------------------------------------------------------------------------
# Test 5 — same age, lower depth does NOT replace (D-07 depth tie-break).
# ---------------------------------------------------------------------------
def test_same_age_depth_tie_break(engine):
    """D-07: same-generation collider at lower depth must NOT replace."""
    n = engine.tt_num_entries()
    h1 = 0
    h2 = n  # collides with h1 on slot 0.

    engine.tt_store(h1, best_move=0xAAAA, score=100, depth=20, flag=TT_EXACT)
    # NO new_search() — generation_ unchanged.
    engine.tt_store(h2, best_move=0xBBBB, score=200, depth=5,  flag=TT_BETA)

    # h1 still wins because new depth (5) < old depth (20) AND age is the same.
    hit, m_out, s_out, d_out, f_out, _age = engine.tt_probe(h1)
    assert hit is True
    assert m_out == 0xAAAA
    assert s_out == 100
    assert d_out == 20
    assert f_out == TT_EXACT

    # And h2 misses — slot still holds h1's encoding.
    hit_h2, *_ = engine.tt_probe(h2)
    assert hit_h2 is False


# ---------------------------------------------------------------------------
# Test 6 — clear() zeroes the table + resets counters.
# ---------------------------------------------------------------------------
def test_clear_zeroes_table(engine):
    """clear() must wipe entries AND reset hit/miss counters."""
    h = 0xFEED_FACE_C0DE_BEEF
    engine.tt_store(h, best_move=0xCCCC, score=77, depth=11, flag=TT_EXACT)
    # Warm the counters.
    engine.tt_probe(h)
    engine.tt_probe(h ^ 0x1)  # different hash → miss

    engine.tt_clear()
    assert engine.tt_hits() == 0
    assert engine.tt_misses() == 0

    hit, *_ = engine.tt_probe(h)
    assert hit is False
    assert engine.tt_hits() == 0
    assert engine.tt_misses() == 1
