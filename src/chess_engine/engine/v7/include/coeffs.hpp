#pragma once

// V7 evaluation coefficients (forward declarations).
//
// Every symbol declared here is DEFINED in src/coeffs.cpp, which is
// generated at build time by tools/gen_coeffs.py from coeffs.json
// (D-10..D-13). src/coeffs.cpp is .gitignored — never commit it.
//
// The set of declarations below MUST stay in lockstep with what
// gen_coeffs.py emits. The emit rule is:
//   - sorted top-level JSON keys (skipping `_*`)
//   - dict-valued keys expand to `{key}_{subkey}` (subkeys also sorted)
//   - list-valued keys/subkeys become `extern const int X[N]`
//   - scalar values become `extern const int X`
//
// If you add a key to coeffs.json, add the matching extern here too.
// Mismatch surfaces as an undefined-symbol error from the v7_engine link
// (caught by every Wave-3 plan's verify gate and by Plan 06's smoke test).
//
// Expected symbol counts (verified by tests/test_v7_eval.py):
//   - 52 total extern declarations
//   - 30 scalar  (material/phase × 6 piece types = 18; bishop_pair × 2;
//                 rook open/semi-open × 2; doubled/isolated/backward × 3;
//                 threats × 3; tempo × 2 = 30)
//   - 22 array   (PSTs 12 × [64]; mobility 8 (4 pieces × 2 phases);
//                 passed_pawn_by_rank [8]; king_attack_table [100])

namespace v7::coeffs {

// --- Scalars: bishop pair, rook on file, pawn structure, threats, tempo ---
extern const int backward_pawn;
extern const int bishop_pair_eg;
extern const int bishop_pair_mg;
extern const int doubled_pawn;
extern const int isolated_pawn;
extern const int rook_open_file;
extern const int rook_semi_open_file;
extern const int tempo_eg;
extern const int tempo_mg;
extern const int threat_minor_by_pawn;
extern const int threat_queen_by_rook;
extern const int threat_rook_by_minor;

// --- Material (mg / eg) ---
extern const int material_eg_B;
extern const int material_eg_K;
extern const int material_eg_N;
extern const int material_eg_P;
extern const int material_eg_Q;
extern const int material_eg_R;
extern const int material_mg_B;
extern const int material_mg_K;
extern const int material_mg_N;
extern const int material_mg_P;
extern const int material_mg_Q;
extern const int material_mg_R;

// --- Phase weights (Pesto) ---
extern const int phase_weights_B;
extern const int phase_weights_K;
extern const int phase_weights_N;
extern const int phase_weights_P;
extern const int phase_weights_Q;
extern const int phase_weights_R;

// --- Piece-square tables (mg / eg), 12 × 64 ---
extern const int pst_eg_B[64];
extern const int pst_eg_K[64];
extern const int pst_eg_N[64];
extern const int pst_eg_P[64];
extern const int pst_eg_Q[64];
extern const int pst_eg_R[64];
extern const int pst_mg_B[64];
extern const int pst_mg_K[64];
extern const int pst_mg_N[64];
extern const int pst_mg_P[64];
extern const int pst_mg_Q[64];
extern const int pst_mg_R[64];

// --- Mobility tables (indexed by attack-count) ---
extern const int mobility_bishop_eg[14];
extern const int mobility_bishop_mg[14];
extern const int mobility_knight_eg[9];
extern const int mobility_knight_mg[9];
extern const int mobility_queen_eg[28];
extern const int mobility_queen_mg[28];
extern const int mobility_rook_eg[15];
extern const int mobility_rook_mg[15];

// --- Passed-pawn bonus by rank (white-relative; rank 0 / 7 = 0) ---
extern const int passed_pawn_by_rank[8];

// --- King attack table (indexed by accumulated attack units, 0..99) ---
extern const int king_attack_table[100];

} // namespace v7::coeffs
