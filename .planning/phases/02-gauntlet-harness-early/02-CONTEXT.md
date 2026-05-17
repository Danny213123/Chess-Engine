# Phase 2: Gauntlet Harness Early - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers an end-to-end SPRT gauntlet harness so V7-vs-V6 strength is measurable as soon as Phase 1 perf bugs are fixed. Scope: fastchess provisioning, a Python runner that drives fastchess + parses results, the V6-vs-V6 sanity probe, and the NPS regression gate. The V7-vs-V6 verdict run itself is deferred until Phase 1 gap-closure lands (see D-09).

</domain>

<decisions>
## Implementation Decisions

### fastchess provisioning (GAUNT-01)
- **D-01:** Use an on-demand fetch script (`tools/fetch_fastchess.py`) modeled on the existing Syzygy download pattern. No binaries committed to git.
- **D-02:** Pin fastchess to a specific upstream release in the script with a SHA256 checksum gate. Bumping versions is a deliberate code change, not implicit.
- **D-03:** Downloaded binary lives in `tools/.cache/fastchess{.exe,}` (gitignored). Re-runs are idempotent — script checks cache + checksum, only downloads on miss.
- **D-04:** Script must select the right artifact per OS (Windows / Linux / macOS). Single entry point; OS detection internal.

### Gauntlet runner shape (GAUNT-02, GAUNT-03, GAUNT-07)
- **D-05:** Python CLI wrapper `tools/gauntlet.py` shells out to fastchess, parses output, persists artifacts. No raw fastchess invocations expected from users.
- **D-06:** Results land in `.planning/gauntlets/{ISO-timestamp}/`. Three artifacts per run:
  - `games.pgn` — full game log for inspection
  - `summary.json` — aggregate W/L/D, Elo, LLR, SPRT verdict, time forfeits (separated per GAUNT-07), per-engine NPS
  - `fastchess.log` — raw stdout/stderr for debugging
- **D-07:** Runner records the exact fastchess command line in `summary.json` so any run is reproducible from the artifact alone (GAUNT-03).

### Time control & concurrency
- **D-08:** Default TC = `10+0.1` (10 s base + 0.1 s increment). One overnight run ≈ 1000 games. Discriminates strength at hobbyist level without being so slow that iteration suffers. Override via CLI flag.
- **D-08a:** Concurrency = 1 always (serialized games). Removes cache/memory contention noise so small Elo deltas remain trustworthy. NPS sentinel runs already require this; making it the default keeps measurements consistent.

### Phase ordering / perf-bug coupling
- **D-09:** Build the harness now. Ship the harness + V6-vs-V6 sanity probe as Phase 2's "complete" signal. Defer the first real V7-vs-V6 SPRT until Phase 1 gap-closure lands the 3 perf bug fixes (engine.cpp:99 depth-cap, search.cpp:267 killers/history reset, search.cpp std::vector PV alloc). Decouples tooling work from engine fix timeline.
- **D-10:** V6-vs-V6 sanity gate (GAUNT-04): tolerance `[-15, +15]` Elo over 200 games. Tight enough to catch harness bias (color-assignment errors, TC asymmetry, book-pairing bugs), loose enough that normal variance doesn't false-positive. ~30-60 min wall clock at 10+0.1 c=1.

### Opening book & SPRT (locked by REQUIREMENTS.md)
- **D-11:** `8moves_v3.pgn` is the opening book (GAUNT-05). Vendor it under `tools/books/` or fetch via the same `tools/.cache/` pattern as fastchess — planner's call.
- **D-12:** Pentanomial SPRT with `elo0=0 elo1=10 alpha=0.05 beta=0.05` (GAUNT-06). Hardcoded in runner; not a per-run flag.

### NPS regression gate (GAUNT-08)
- **D-13:** Runner emits per-engine NPS in `summary.json`. A separate pytest sentinel (extending the Phase 1 `test_nps_sentinel`) reads the latest gauntlet `summary.json` and fails if V7 NPS < 0.8 × V6 NPS on the same fixed position. This sentinel runs under `RUN_BENCHMARKS=1`, not on every pytest invocation.

### Claude's Discretion
- Exact module layout under `tools/` (single file vs subpackage).
- Whether `tools/gauntlet.py` exposes subcommands (`run`, `sanity`, `report`) or distinct scripts.
- Internal fastchess CLI flag wiring (so long as the persisted command line is reproducible per D-07).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — Phase 2 requirements GAUNT-01..08
- `.planning/ROADMAP.md` — Phase 2 sits between Phase 1 (V7 skeleton) and Phase 3 (strength work)

### Phase 1 outputs the harness measures
- `src/chess_engine/engine/v7/` — V7 native module under measurement
- `src/chess_engine/engine/v6/` — V6 baseline opponent
- `.planning/phases/01-skeleton-smoke/.continue-here.md` — UCI binary build steps (`v7_uci` CMake target); the gauntlet drives fastchess against `v7_uci` + V6's equivalent

### Known issues affecting Phase 2
- `memory/project_phase1_known_perf_bugs.md` — three V7 perf bugs that make V7-vs-V6 SPRT meaningless until fixed (see D-09)

### External tools
- fastchess upstream — https://github.com/Disservin/fastchess (version pin TBD by planner; script must record it)
- Pentanomial SPRT theory — fastchess docs are sufficient; no extra reading required

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Syzygy download script pattern** (from Phase 1 Plan 05): existing example of "fetch big binary, checksum, cache outside git" — `tools/fetch_fastchess.py` should mirror its shape (idempotent, OS-aware, checksum-gated).
- **`test_nps_sentinel`** (Phase 1, `tests/test_v7_engine.py`): existing single-position NPS measurement. Phase 2 NPS regression gate (D-13) extends this to read from `summary.json` rather than re-running positions inline.
- **`v7_uci` CMake target** (Phase 1 Plan 06): standalone UCI binary. fastchess drives it directly — no Python wrapper in the gauntlet hot loop.
- **V6 native module**: already has its own UCI surface (verify in planning); reuse rather than re-implement an adapter.

### Established Patterns
- **`.planning/` for non-code artifacts**: gauntlet results land in `.planning/gauntlets/` rather than a top-level `gauntlet-results/`, consistent with how plans/research/state live there.
- **uv-managed Python tooling**: `tools/gauntlet.py` runs under `python3 -m uv run --group dev`. Avoid introducing a separate venv or pinning new top-level deps unless required.
- **Pytest sentinels gated by env var**: `RUN_BENCHMARKS=1` already gates expensive perf tests. NPS regression check follows the same gate.

### Integration Points
- **Gauntlet runner ↔ fastchess binary**: `tools/.cache/fastchess` resolved by `fetch_fastchess.py` (idempotent on every `gauntlet.py` invocation).
- **Gauntlet runner ↔ v7_uci / v6 UCI binaries**: subprocess; identical UCI options (`Hash`, `Threads`) per GAUNT-03.
- **Phase 1 gap-closure → Phase 2 verdict run**: gating handshake. Verdict run kicked off only after gap-closure lands (D-09).

</code_context>

<specifics>
## Specific Ideas

- Reuse the Syzygy fetch script as the template for `fetch_fastchess.py`: same file shape, same idempotency check, same cache directory convention.
- `summary.json` must record the literal fastchess command line so a year-old gauntlet can be re-run bit-for-bit (D-07).
- V6-vs-V6 sanity (D-10) is the harness's own correctness test — must pass before any V7 result is reported.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-host distributed gauntlet runs**: out of scope. Single-host serialized runs are sufficient at this engine strength tier.
- **Web UI for gauntlet results**: not in REQUIREMENTS; results are JSON+PGN files inspected manually or by CI.
- **Auto-tuning loop driven by gauntlet results**: belongs in a later strength-work phase (Phase 3+), not the harness phase.
- **Cross-engine gauntlets (V7 vs Stockfish/etc.)**: out of scope. Phase 2 is V7-vs-V6 only per GAUNT-03/04.

</deferred>

---

*Phase: 2-Gauntlet Harness Early*
*Context gathered: 2026-05-16*
