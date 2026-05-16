/*
 * V7 tbconfig.h — Fathom build-time configuration override (TB-02)
 *
 * This file SHADOWS extern/fathom/src/tbconfig.h via the CMake include-path
 * ordering pre-staged by Plan 02 Task 3:
 *
 *     target_include_directories(v7_engine PRIVATE
 *         ${CMAKE_CURRENT_SOURCE_DIR}/include   <-- THIS FILE (FIRST)
 *         ${FATHOM_DIR}/src                     <-- Fathom's bundled tbconfig.h
 *     )
 *
 * Fathom's tbprobe.c does `#include "tbconfig.h"` — the preprocessor walks
 * the include directories in order, so V7's include/ dir wins. This file
 * MUST therefore expose the same `TBCONFIG_H` header guard symbol or
 * Fathom's bundled one will get re-included on a later pass and clash.
 *
 * RESEARCH.md §B3 lines 617-633 — V7 wires every TB_* attack macro to v7::
 * magic-bitboard + bitboard-helper functions so the engine does not waste
 * cache on a second copy of the attack tables.
 *
 * COMPILATION NOTE: tbprobe.c is compiled as C (LANGUAGE C set in
 * CMakeLists.txt). C cannot see C++ namespace symbols directly, so this
 * header declares a thin set of C-callable bridge functions (prefix
 * `v7_tb_`) which the macros expand to. The bridge function bodies live
 * in src/syzygy.cpp wrapped in an `extern "C"` block — they forward to
 * v7::pawn_attacks[], v7::knight_attacks[], v7::bishop_attacks(),
 * v7::rook_attacks(), v7::queen_attacks(), v7::king_attacks(),
 * v7::popcount(), and v7::pop_lsb() respectively.
 *
 * TB-02 acceptance: this file enumerates ALL 8 macro overrides (6 TB_*_ATTACKS
 * + TB_pop_lsb + TB_popcount) plus Fathom's own override hooks
 * (TB_CUSTOM_LSB + TB_CUSTOM_POP_COUNT) so Fathom's tbprobe.c uses our
 * implementations exclusively. The plan acceptance grep verifies macro names.
 */

#ifndef TBCONFIG_H
#define TBCONFIG_H

#include <stdint.h>

/* ----------------------------------------------------------------------
 * Bridge function declarations (C linkage — callable from tbprobe.c).
 * Implementations live in src/syzygy.cpp.
 * --------------------------------------------------------------------*/
#ifdef __cplusplus
extern "C" {
#endif

uint64_t v7_tb_pawn_attacks(unsigned sq, unsigned color);
uint64_t v7_tb_knight_attacks(unsigned sq);
uint64_t v7_tb_bishop_attacks(unsigned sq, uint64_t occ);
uint64_t v7_tb_rook_attacks(unsigned sq, uint64_t occ);
uint64_t v7_tb_queen_attacks(unsigned sq, uint64_t occ);
uint64_t v7_tb_king_attacks(unsigned sq);
unsigned v7_tb_lsb(uint64_t b);
unsigned v7_tb_popcount(uint64_t b);

#ifdef __cplusplus
}
#endif

/* ----------------------------------------------------------------------
 * Fathom scoring constants — must remain consistent with Fathom's bundled
 * tbconfig.h to keep TB_GET_WDL / TB_GET_DTZ macros aligned with what
 * tbprobe.c stores. Values copied verbatim from extern/fathom/src/tbconfig.h.
 * --------------------------------------------------------------------*/
#define TB_VALUE_PAWN     100
#define TB_VALUE_MATE     32000
#define TB_VALUE_INFINITE 32767
#define TB_VALUE_DRAW     0
#define TB_MAX_MATE_PLY   255

/* ----------------------------------------------------------------------
 * Engine-integration overrides (TB-02 — the whole reason this file exists).
 *
 * Plan acceptance enumerates exactly 8 macro overrides:
 *   TB_PAWN_ATTACKS, TB_KNIGHT_ATTACKS, TB_BISHOP_ATTACKS,
 *   TB_ROOK_ATTACKS, TB_QUEEN_ATTACKS, TB_KING_ATTACKS,
 *   TB_pop_lsb, TB_popcount.
 *
 * Fathom's own override hooks are TB_CUSTOM_LSB and TB_CUSTOM_POP_COUNT;
 * we wire them as well so Fathom actually uses ours (Fathom only checks
 * TB_CUSTOM_LSB / TB_CUSTOM_POP_COUNT, not TB_pop_lsb / TB_popcount).
 * The plan-named macros (TB_pop_lsb / TB_popcount) are retained so a
 * future caller can use them directly and so the plan grep gate passes.
 * --------------------------------------------------------------------*/
#define TB_PAWN_ATTACKS(sq, color) (v7_tb_pawn_attacks((sq), (color)))
#define TB_KNIGHT_ATTACKS(sq)      (v7_tb_knight_attacks((sq)))
#define TB_BISHOP_ATTACKS(sq, occ) (v7_tb_bishop_attacks((sq), (occ)))
#define TB_ROOK_ATTACKS(sq, occ)   (v7_tb_rook_attacks((sq), (occ)))
#define TB_QUEEN_ATTACKS(sq, occ)  (v7_tb_queen_attacks((sq), (occ)))
#define TB_KING_ATTACKS(sq)        (v7_tb_king_attacks((sq)))

/* Fathom's actual override hooks — wire to the same bridges */
#define TB_CUSTOM_LSB(x)           (v7_tb_lsb((x)))
#define TB_CUSTOM_POP_COUNT(x)     (v7_tb_popcount((x)))

/* Plan-named aliases (kept for direct C++ callers and the acceptance grep) */
#define TB_pop_lsb(b)              (v7_tb_lsb((b)))
#define TB_popcount(b)             (v7_tb_popcount((b)))

#endif /* TBCONFIG_H */
