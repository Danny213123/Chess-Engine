# tools/books/ — provenance

This directory holds the opening-book seed consumed by every Phase 2 gauntlet
(per Plan 02-04b `resolve_opening_book()`). Provisioning lives in EITHER of two
modes; the resolver consumes whichever is present.

| Mode | File present | Behavior |
| --- | --- | --- |
| Vendored (preferred when license is compatible) | `tools/books/8moves_v3.pgn` | Resolver reads directly. No network. |
| Fetch-fallback (when vendoring is blocked) | `tools/books/.fetch_fallback.json` | Resolver runs the same SHA256-gated download flow that `tools/fetch_fastchess.py` uses for the fastchess binary. |

`8moves_v3.pgn` and `.fetch_fallback.json` are mutually exclusive — never both.

---

## Upstream source

- **Project:** official-stockfish/books
- **URL:** https://github.com/official-stockfish/books
- **Asset:** `8moves_v3.pgn.zip` (raw: https://github.com/official-stockfish/books/raw/master/8moves_v3.pgn.zip)
- **Upstream commit SHA (pinned at vendor time):** PENDING_HUMAN_CHECKPOINT — must be filled by the operator who lands the real `.fetch_fallback.json.sha256` value (or who completes the vendored sub-A path). Record via `git ls-remote https://github.com/official-stockfish/books refs/heads/master | awk '{print $1}'`.
- **Approximate position count:** ~34,700
- **Ply depth:** 16

## Vendor / fetch date

- 2026-05-16 — executor wrote `.fetch_fallback.json` in fallback mode with sentinel sha256.
- Subsequent human checkpoint pass MUST update both the manifest sha256 AND the "Upstream commit SHA" line above.

## License

The full upstream LICENSE text was NOT inspected during this execution because the worktree environment had no network egress at execution time. The operator who lands the real sha256 (per the Outstanding item in `02-03-SUMMARY.md`) MUST inspect `https://github.com/official-stockfish/books/blob/master/LICENSE` and either:

1. Quote the full LICENSE text here AND switch Final Provisioning Mode to "VENDORED" (committing the unzipped `8moves_v3.pgn` and deleting `.fetch_fallback.json`), OR
2. Quote the relevant LICENSE clauses that block vendoring AND keep "FALLBACK MANIFEST" mode (leaving `.fetch_fallback.json` in place with a real sha256).

Acceptable upstream licenses for the VENDORED path: MIT, BSD-2/3, Apache-2.0, CC0, public-domain.
Not acceptable without explicit user opt-in: GPL-3.0, AGPL.

## License Compatibility Decision

FALLBACK MANIFEST — pending license inspection. Executor deferred the inspection (no network); fallback manifest written defensively so Plan 02-04b's resolver has *some* contract to point at. The decision must be re-made by the operator who lands the real sha256.

## Final Provisioning Mode

**fetch-fallback at `tools/books/.fetch_fallback.json`** (this file exists; `8moves_v3.pgn` does NOT).

## Consumers

- `tools/gauntlet.py` (Plan 02-04b) — `resolve_opening_book()` reads either path transparently. Will SystemExit if the manifest sha256 is still the sentinel literal, matching the D-02 trust-gate pattern used by `tools/fetch_fastchess.py`.
