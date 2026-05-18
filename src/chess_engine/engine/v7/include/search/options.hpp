#pragma once

namespace v7 {

// =============================================================================
// ENGINE OPTIONS (D-06) — 12 per-refinement UCI toggles
// =============================================================================
//
// Created by Plan 03-01 Task 2 as the cross-Wave-2 scaffold so Plans
// 03-02/03-03/03-04 can all reference a stable EngineOptions type without
// each plan re-introducing a shared struct.
//
// Default ON for all Tier-1 (Plan 03-02) and Tier-2 (Plan 03-03) refinements.
// UseFortressEval defaults OFF per D-11: a separate validation gauntlet
// inside Plan 03-04 decides whether it ships as default-ON.
//
// Engine::set_option(name, value) parses UCI "setoption name X value Y"
// and writes into the Engine's EngineOptions instance (see engine.cpp).
// Search functions gate each refinement with `if (info.options && info.options->UseXxx)`.
//
// Consuming plans:
//   - Plan 03-02: UseNullMove, UseLMR, UseRFP, UseFutility, UseLMP, UseIIR,
//                 UseCheckExt, UseRecaptureExt (Tier-1)
//   - Plan 03-03: UseSingular, UseMultiCut, UseProbCut (Tier-2)
//   - Plan 03-04: UseFortressEval (endgame, default OFF per D-11)

struct EngineOptions {
    // Tier-1 (Plan 03-02 consumers)
    bool UseNullMove     = true;   // Adaptive null-move pruning (SRCH-03)
    bool UseLMR          = true;   // Late Move Reductions (SRCH-04)
    bool UseRFP          = true;   // Reverse Futility Pruning (SRCH-05)
    bool UseFutility     = true;   // Futility Pruning (SRCH-05)
    bool UseLMP          = true;   // Late Move Pruning (SRCH-05)
    bool UseIIR          = true;   // Internal Iterative Reduction (SRCH-11)
    bool UseCheckExt     = true;   // Check extension (SRCH-12)
    bool UseRecaptureExt = true;   // Recapture extension (SRCH-12)

    // Tier-2 (Plan 03-03 consumers)
    bool UseSingular     = true;   // Singular extensions (SRCH-08)
    bool UseMultiCut     = true;   // Multi-cut pruning (SRCH-09)
    bool UseProbCut      = true;   // ProbCut (SRCH-10; may flip to false at Plan 03-03 T3 checkpoint)

    // Endgame (Plan 03-04 consumer)
    bool UseFortressEval = false;  // D-11: conservative fortress hints; default OFF,
                                   // ship as ON only if Plan 03-04 validation gauntlet passes

    // Plan 04-01 D-04 — Lazy SMP thread count (valid range [1, 256])
    int Threads = 1;  // default 1 = single-threaded (Threads=N spawns N-1 helper threads)
};

} // namespace v7
