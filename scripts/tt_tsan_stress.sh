#!/usr/bin/env bash
# PAR-03 TSan stress harness for V7 lockless TT.
# Stub created by Plan 03-01; full implementation in Plan 03-05 per CONTEXT D-08.
#
# Plan 03-05 will implement:
#   1. Build V7's lockless TT standalone harness with -fsanitize=thread
#   2. Run 16 threads × 60 seconds of randomized probe/store
#   3. Report PASS/FAIL based on ThreadSanitizer output
#
# Requirements (when Plan 03-05 implements):
#   - clang or gcc with TSan support (NOT MSVC — runs on WSL/Linux/macOS per D-08)
#   - Blocking human checkpoint at end of Phase 3
#
# Exit codes:
#   0  = TSan clean (PASS)
#   1  = TSan reported races (FAIL)
#   78 = EX_CONFIG — stub not yet implemented (Plan 03-05)

echo "tt_tsan_stress.sh: stub — Plan 03-05 will implement" >&2
exit 78  # EX_CONFIG — distinguishable from real failures (0=pass, 1=fail)
