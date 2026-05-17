# Phase 2: Gauntlet Harness Early - Research

**Researched:** 2026-05-16
**Domain:** fastchess SPRT gauntlet tooling (Python wrapper + binary fetch + V6/V7 UCI integration)
**Confidence:** HIGH (fastchess surface, output format, opening book) / MEDIUM (release pin — no checksums published upstream) / **BLOCKING UNKNOWN: V6 has no standalone UCI binary**

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `tools/fetch_fastchess.py` modeled on the existing Syzygy download pattern. No binaries committed to git.
- **D-02:** Pin fastchess to a specific upstream release in the script with a SHA256 checksum gate. Bumping versions is a deliberate code change.
- **D-03:** Downloaded binary at `tools/.cache/fastchess{.exe,}` (gitignored). Idempotent: script checks cache + checksum, only downloads on miss.
- **D-04:** Script selects right artifact per OS (Windows / Linux / macOS). Single entry point; OS detection internal.
- **D-05:** Python CLI wrapper `tools/gauntlet.py` shells out to fastchess. No raw fastchess invocations expected from users.
- **D-06:** Results land in `.planning/gauntlets/{ISO-timestamp}/`. Three artifacts per run: `games.pgn`, `summary.json`, `fastchess.log`.
- **D-07:** Runner records the exact fastchess command line in `summary.json` (GAUNT-03 reproducibility).
- **D-08:** Default TC = `10+0.1`. Override via CLI flag.
- **D-08a:** Concurrency = 1 always (serialized games).
- **D-09:** Ship harness + V6-vs-V6 sanity probe as Phase 2's "complete" signal. Defer first real V7-vs-V6 SPRT until Phase 1 gap-closure lands the 3 perf bugs.
- **D-10:** V6-vs-V6 sanity gate (GAUNT-04): tolerance `[-15, +15]` Elo over 200 games.
- **D-11:** `8moves_v3.pgn` is the opening book (GAUNT-05). Vendor under `tools/books/` or fetch via `tools/.cache/` — planner's call.
- **D-12:** Pentanomial SPRT with `elo0=0 elo1=10 alpha=0.05 beta=0.05` (GAUNT-06). Hardcoded in runner; not a per-run flag.
- **D-13:** Runner emits per-engine NPS in `summary.json`. Separate pytest sentinel extending Phase 1 `test_nps_sentinel` reads latest `summary.json` and fails if V7 NPS < 0.8 × V6 NPS on same fixed position. Gated by `RUN_BENCHMARKS=1`.

### Claude's Discretion

- Exact module layout under `tools/` (single file vs subpackage).
- Whether `tools/gauntlet.py` exposes subcommands (`run`, `sanity`, `report`) or distinct scripts.
- Internal fastchess CLI flag wiring (so long as the persisted command line is reproducible per D-07).

### Deferred Ideas (OUT OF SCOPE)

- Multi-host distributed gauntlet runs.
- Web UI for gauntlet results.
- Auto-tuning loop driven by gauntlet results.
- Cross-engine gauntlets (V7 vs Stockfish/etc.) — V7-vs-V6 only.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GAUNT-01 | fastchess prebuilt binary fetched by script | §2 (CLI surface) + §3 (release pin) + §6 (Syzygy template) |
| GAUNT-02 | `v7_uci` exposes minimal UCI surface (uci/isready/setoption/position/go/stop/quit) sufficient for fastchess | §7 (V6/V7 UCI binary status) — **v7_uci silently ignores `setoption`; V6 has no UCI binary at all** |
| GAUNT-03 | Identical Hash/Threads/TC; exact fastchess command persisted in result file | §2 (`-engine option.*` flags) + §4 (summary.json schema) |
| GAUNT-04 | V6-vs-V6 sanity probe ≈ 0 Elo before V7-vs-V6 trusted | §2 (SPRT flags), §10 (validation) |
| GAUNT-05 | Opening book seeding via `8moves_v3.pgn` | §5 (source + vendor strategy) |
| GAUNT-06 | Pentanomial SPRT with `elo0=0 elo1=10 alpha=0.05 beta=0.05` | §2 (canonical command line) |
| GAUNT-07 | Time forfeits flagged separately from losses | §4 (PGN `[Termination]` tag parse) + §10 (validation) |
| GAUNT-08 | Build fails if V7 NPS drops >20% vs V6 on same hardware | §8 (NPS extraction) + §10 (validation) |

</phase_requirements>

## 1. Executive Summary

- **fastchess CLI surface is settled and stable.** [VERIFIED via official man.md and chessprogramming wiki] The pentanomial SPRT command line composes from `-engine`, `-each tc=`, `-openings file=`, `-sprt elo0=N elo1=M alpha=A beta=B`, `-rounds`, `-concurrency`, `-pgnout`, `-report penta=true`. A representative full command is below in §2.
- **Pin a recent Disservin/fastchess release; compute SHA256 on first download.** [VERIFIED: releases page exists; CITED: upstream does not publish SHA256s in release notes] Strategy: hardcode the chosen version tag + per-OS asset filename, hardcode SHA256s recorded once locally, verify on every fetch. Asset format/filenames must be confirmed against the chosen tag at planning time.
- **Output parsing path is regex over fastchess stdout** [VERIFIED via dogeystamp blog + fishtest's `games.py`]. The 5 lines per progress block (`Elo |`, `SPRT |`, `LLR |`, `Games |`, `Penta |`) are stable and machine-parseable. Verdict = `LLR ≥ upper_bound` (H1) / `LLR ≤ lower_bound` (H0) / between (continue). Time forfeits are NOT in the SPRT block — they appear in the PGN's `[Termination]` tag and in the per-game stdout lines.
- **`8moves_v3.pgn` canonical source is `github.com/official-stockfish/books`** [VERIFIED]. ~34,700 positions, distributed as `.pgn.zip`. Small enough (~hundreds of KB compressed) to vendor in-repo under `tools/books/`. Recommendation: vendor, not fetch — it's the only PGN we need and avoids a second network dependency at gauntlet run time.
- **BLOCKING gap for V7-vs-V6: V6 has no standalone UCI binary.** [VERIFIED in code] V6's `CMakeLists.txt` builds only the `v6_engine` pybind11 module. fastchess needs a process to `exec`. **Planner MUST address:** add a `v6_uci` CMake target (mirror Phase 1's `v7_uci` pattern) as the very first work item, OR write a thin Python UCI shim that wraps the v6 pybind11 module. The pybind11 shim approach has process-spawn overhead and breaks the "real C++ binary playing real chess" gauntlet shape. **Strong recommendation: add `v6_uci` CMake target.**
- **Additional gap: `v7_uci` silently ignores `setoption`.** [VERIFIED in `src/chess_engine/engine/v7/src/uci_main.cpp` line 207-210] Phase 1's UCI loop documents "Phase 4 will add setoption Threads/Hash/SyzygyPath." For Phase 2's V7-vs-V6 verdict (GAUNT-03 requires identical Hash + Threads), `v7_uci` MUST accept at minimum `setoption name Hash value N` and `setoption name Threads value N` — even if it accepts and discards them silently for now, fastchess sends them and expects no error response. Planner should add a minimal `setoption` parser (accept + ignore unknown names; accept + apply Hash via the binding if exposed).

**Primary recommendation:** Plan Phase 2 as three sequential work units: (1) **prerequisite gap-closure**: add `v6_uci` target + minimal `setoption` parser to `v7_uci`; (2) **harness build**: `tools/fetch_fastchess.py` + `tools/gauntlet.py` + book vendoring + `summary.json` schema; (3) **validation**: V6-vs-V6 sanity run + `RUN_BENCHMARKS=1` NPS sentinel pytest. The first V7-vs-V6 SPRT verdict run is explicitly deferred (D-09).

## 2. fastchess CLI Surface for SPRT

### Required flags for a pentanomial SPRT V7-vs-V6 run at D-08/D-08a/D-12

[VERIFIED: official fastchess man.md + chessprogramming wiki + dogeystamp guide + ijccrl guide]

| Flag | Value for this project | Purpose |
|------|------------------------|---------|
| `-engine cmd=... name=v7 option.Hash=N option.Threads=1` | `v7_uci` binary path | Engine A |
| `-engine cmd=... name=v6 option.Hash=N option.Threads=1` | `v6_uci` binary path | Engine B |
| `-each tc=10+0.1` | D-08 | Shared time control |
| `-openings file=tools/books/8moves_v3.pgn format=pgn order=random` | D-11 | Opening book seeding |
| `-rounds 5000` | Large upper bound | SPRT terminates early; this is just a cap |
| `-repeat` | required for paired games | Plays both colors with same opening (pentanomial requires this) |
| `-concurrency 1` | D-08a | Single game at a time, removes cache/memory contention |
| `-sprt elo0=0 elo1=10 alpha=0.05 beta=0.05` | D-12 | Hardcoded pentanomial bounds |
| `-report penta=true` | required to emit `Penta` line | Pentanomial reporting in stdout |
| `-pgnout file=games.pgn notation=san nodes=true nps=true tbhits=true` | D-06 | Full PGN with per-move NPS for D-13 |
| `-output format=fastchess` | default | Default fastchess stdout format (regex-friendly) |
| `-ratinginterval 10 -scoreinterval 10` | print stats every 10 games | Frequent progress; lets the wrapper stream LLR |
| `-log file=fastchess.log` | D-06 | Captures fastchess's own debug log |
| `-recover` | recommended | If an engine crashes mid-game, continue the match (skip that game) |
| `-randomseed` | recommended | Deterministic-by-default seed; use a fixed value for reproducibility (D-07) |

### Representative full command line

```bash
tools/.cache/fastchess \
  -engine cmd=src/chess_engine/engine/v7/build/v7_uci name=v7 \
          option.Hash=64 option.Threads=1 \
  -engine cmd=src/chess_engine/engine/v6/build/v6_uci name=v6 \
          option.Hash=64 option.Threads=1 \
  -each tc=10+0.1 \
  -openings file=tools/books/8moves_v3.pgn format=pgn order=random plies=16 \
  -rounds 5000 -repeat -concurrency 1 -recover \
  -sprt elo0=0 elo1=10 alpha=0.05 beta=0.05 \
  -report penta=true \
  -ratinginterval 10 -scoreinterval 10 \
  -pgnout file=.planning/gauntlets/2026-05-16T21-00-00Z/games.pgn \
          notation=san nodes=true nps=true tbhits=true \
  -log file=.planning/gauntlets/2026-05-16T21-00-00Z/fastchess.log
```

**For the V6-vs-V6 sanity (D-10):** same shape, both engines point to `v6_uci`, override `-rounds 200`, optionally drop `-sprt` and run a fixed-N tournament so the harness measures Elo over exactly 200 games regardless of SPRT termination. (SPRT on identical engines never terminates — LLR drifts around zero forever.)

### Adjudication flags (planner discretion)

The man.md canonical example includes `-resign movecount=3 score=600` and `-draw movenumber=34 movecount=8 score=20`. These shorten matches significantly but are **not required** for Phase 2 — and could mask V7 endgame weakness if applied too aggressively. **Recommendation: omit for V6-vs-V6 sanity (cleanest signal), add conservative `-draw movenumber=60 movecount=10 score=10` only for V7-vs-V6 verdict runs to avoid pathologically-long 100-move draws.** Document in the plan that adjudication is a tunable knob.

## 3. Pinned Release Selection

[VERIFIED: releases exist at https://github.com/Disservin/fastchess/releases. ASSUMED: exact filename/SHA256 strategy — these are not published in release notes.]

**Recommendation: pin to the latest stable release at planning time.** Fastchess ships multi-platform builds (Windows x86_64 `.exe`, Linux x86_64, macOS, plus ARM/RISC-V variants). Filenames follow a `fastchess-{platform}-{arch}.{ext}` convention but the exact pattern varies per release — confirm by querying the GitHub releases API at planning time:

```bash
curl -s https://api.github.com/repos/Disservin/fastchess/releases/latest | \
  jq '{tag: .tag_name, assets: [.assets[] | {name, url: .browser_download_url, size}]}'
```

### Checksum strategy (D-02)

**Upstream does not publish SHA256s in release notes.** [CITED: fastchess GitHub releases page] Strategy:

1. Planner picks a tag at plan time (e.g. `v1.4.0` if available).
2. Plan author downloads each per-OS asset manually once, computes `sha256sum`, records the hashes in a Python dict in `fetch_fastchess.py`:
   ```python
   FASTCHESS_RELEASE = "v1.4.0"  # PIN: bump deliberately
   FASTCHESS_ASSETS = {
       "Windows": {
           "asset": "fastchess-windows-x86_64.exe",
           "sha256": "abc123...",  # computed locally; see CONTRIBUTING note
       },
       "Linux":   {"asset": "fastchess-linux-x86_64",      "sha256": "..."},
       "Darwin":  {"asset": "fastchess-macos-x86_64",       "sha256": "..."},
   }
   ```
3. Fetch script downloads asset, verifies SHA256 before placing in `tools/.cache/`, raises a clear error on mismatch.
4. Bumping the version is a 4-line PR (tag + 3 SHA256s) — deliberate, reviewable, audited.

**Document in the plan:** the SHA256s come from a one-time manual `sha256sum` after download from a trusted browser session, not from upstream. This is the same trust model `pip` uses for unsigned wheels.

## 4. Output Parsing Strategy

[VERIFIED: dogeystamp.com SPRT guide + chessprogramming wiki + Stockfish fishtest `games.py` is the battle-tested reference parser]

### What's where

| Datum | Source | Format |
|-------|--------|--------|
| Elo estimate + error | fastchess stdout | `Elo  \| 13.87 +- 7.58 (95%)` |
| LLR + bounds + SPRT bounds | fastchess stdout | `LLR  \| 2.90 (-2.25, 2.89) [0.00, 5.00]` |
| W/L/D counts | fastchess stdout | `Games \| N: 4186 W: 1197 L: 1030 D: 1959` |
| Pentanomial counts | fastchess stdout | `Penta \| [130, 455, 782, 570, 156]` (LL, LD, WL+DD, WD, WW) |
| Per-move NPS | PGN `nps=true` comments | `{ ... nps=850432 }` PGN tail-comments |
| Time forfeits | PGN `[Termination]` tag | `[Termination "time forfeit"]` (CITED: cutechess-compatible convention; verify against actual fastchess output during implementation) |
| SPRT verdict | computed from LLR | `H1` if LLR ≥ upper, `H0` if LLR ≤ lower, else `inconclusive` |

### Parsing approach (regex; minimal, robust)

```python
LINE_PATTERNS = {
    "elo":   r"^Elo\s*\|\s*(-?\d+\.\d+)\s*\+-\s*(\d+\.\d+)\s*\((\d+)%\)",
    "llr":   r"^LLR\s*\|\s*(-?\d+\.\d+)\s*\((-?\d+\.\d+),\s*(-?\d+\.\d+)\)\s*\[(-?\d+\.\d+),\s*(-?\d+\.\d+)\]",
    "games": r"^Games\s*\|\s*N:\s*(\d+)\s*W:\s*(\d+)\s*L:\s*(\d+)\s*D:\s*(\d+)",
    "penta": r"^Penta\s*\|\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]",
}
```

Keep the **last** match of each pattern as it streams (the final progress block is the authoritative one). At process exit, compute verdict from `(llr, lower_bound, upper_bound)`.

### `summary.json` schema (proposed for D-06/D-07)

```json
{
  "schema_version": 1,
  "timestamp_utc": "2026-05-16T21:00:00Z",
  "engines": {
    "v7": {"cmd": ".../v7_uci", "git_sha": "abc1234", "options": {"Hash": 64, "Threads": 1}},
    "v6": {"cmd": ".../v6_uci", "git_sha": "abc1234", "options": {"Hash": 64, "Threads": 1}}
  },
  "tc": "10+0.1",
  "concurrency": 1,
  "openings": {"file": "tools/books/8moves_v3.pgn", "format": "pgn", "order": "random"},
  "sprt": {"elo0": 0, "elo1": 10, "alpha": 0.05, "beta": 0.05},
  "fastchess_command": ["tools/.cache/fastchess", "-engine", "...", ...],
  "fastchess_version": "v1.4.0",
  "host": {"os": "Windows", "cpu": "...", "cores": 8},
  "result": {
    "verdict": "H1" | "H0" | "inconclusive" | "interrupted",
    "elo": 13.87, "elo_err": 7.58, "elo_ci": 95,
    "llr": 2.90, "llr_lower": -2.25, "llr_upper": 2.89,
    "games": {"n": 4186, "w": 1197, "l": 1030, "d": 1959},
    "penta": [130, 455, 782, 570, 156],
    "time_forfeits": {"v7": 0, "v6": 2}
  },
  "nps": {
    "v7": {"median": 528000, "mean": 540123, "samples": 1197},
    "v6": {"median": 612000, "mean": 624500, "samples": 1030}
  }
}
```

The `nps.{engine}.median` field is what the D-13 pytest sentinel reads.

### Per-game W/L/D + time-forfeit extraction

fastchess prints per-game lines like `Finished game N (engineA vs engineB): result reason`. To distinguish a time forfeit from a normal loss, the cleanest path is to **parse the PGN's `[Termination]` header**: cutechess and fastchess both emit values like `"time forfeit"`, `"illegal move"`, `"disconnected"`, `"adjudicated"`, etc. The runner walks `games.pgn` after fastchess exits and tallies time forfeits per engine — that satisfies GAUNT-07 cleanly. **VERIFY THIS** during implementation by running a contrived game with an artificial time loss; the exact Termination string is the only thing we can't be 100% certain of from documentation alone.

## 5. Opening Book Sourcing (D-11)

[VERIFIED: github.com/official-stockfish/books]

- **Canonical source:** `https://github.com/official-stockfish/books/blob/master/8moves_v3.pgn.zip`
- **Contents:** 34,700 positions, 16 plies / 8 moves deep
- **Distribution:** distributed as `.pgn.zip`; the unzipped `.pgn` is the input to fastchess
- **License:** check the repo's LICENSE at planning time (Stockfish books are typically permissive — GPL-aligned with Stockfish itself; verify before vendoring)

### Vendor vs fetch tradeoff

| | Vendor in repo (`tools/books/8moves_v3.pgn`) | Fetch via `tools/.cache/8moves_v3.pgn` |
|--|--|--|
| Repo size impact | adds ~1-2 MB uncompressed PGN once | zero |
| Offline runs | works | broken without prior fetch |
| Reproducibility (D-07) | trivially exact — `git log` shows version | requires checksum in fetch script |
| Setup steps | one fewer | one more |

**Recommendation: vendor under `tools/books/8moves_v3.pgn` (commit the unzipped PGN).** The file is small enough that the repo-size cost is negligible, and it removes a network dependency from every gauntlet invocation. The Stockfish books repo is the upstream of record; pin the source URL + commit SHA in a `tools/books/SOURCES.md` for provenance.

(Planner discretion per D-11. If the planner prefers fetch-on-demand, mirror the `fetch_fastchess.py` shape — same checksum gate, same `tools/.cache/` location.)

## 6. Syzygy Fetch Script — Template Notes

[VERIFIED: searched `tools/`, `scripts/`, repo root, and `src/`]

**Finding:** The "Syzygy download script" referenced in D-01 / 02-CONTEXT.md does NOT exist as a standalone script in the repo. What exists:

- `cli/src/index.js::syzygyDownload()` — a Node CLI subcommand (`chess-engine syzygy download`) that resolves the OS-aware default path, writes the path to `.chess-engine.json`, and **for Phase 1 only shells out to a one-file dry-run / single-shot `curl` against `https://tablebase.lichess.ovh/tables/standard/3-4-5/`**. It is not the "fetch big binary, checksum, cache" pattern at all — it's a destination resolver + shell wrapper.

**Implication:** D-01's framing ("model on existing Syzygy download pattern") is aspirational; there is no existing Python fetch+checksum module to clone. The planner has to design `fetch_fastchess.py` from scratch. The good news: the shape is well-understood from the broader ecosystem (`pip`, `conda`, `setup.py download_url` patterns).

### Recommended `fetch_fastchess.py` shape (canonical idempotent fetch+checksum module)

```python
#!/usr/bin/env python3
"""Fetch + cache + checksum-verify fastchess binary.

Idempotent: re-runs are no-ops when the cached binary matches the pinned SHA256.
"""
from __future__ import annotations
import hashlib, os, platform, stat, sys, urllib.request
from pathlib import Path

FASTCHESS_RELEASE = "v1.4.0"  # PIN — bump deliberately
FASTCHESS_ASSETS = {
    "Windows": {"asset": "fastchess-windows-x86_64.exe", "sha256": "..."},
    "Linux":   {"asset": "fastchess-linux-x86_64",       "sha256": "..."},
    "Darwin":  {"asset": "fastchess-macos-x86_64",        "sha256": "..."},
}
CACHE_DIR = Path(__file__).resolve().parent / ".cache"

def _asset_for_host() -> tuple[str, str]:
    spec = FASTCHESS_ASSETS.get(platform.system())
    if spec is None:
        raise SystemExit(f"Unsupported OS: {platform.system()}")
    return spec["asset"], spec["sha256"]

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_fastchess() -> Path:
    asset, want_sha = _asset_for_host()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = CACHE_DIR / ("fastchess.exe" if platform.system() == "Windows" else "fastchess")
    if dest.exists() and _sha256(dest) == want_sha:
        return dest                              # idempotent fast path
    url = f"https://github.com/Disservin/fastchess/releases/download/{FASTCHESS_RELEASE}/{asset}"
    print(f"[fetch_fastchess] downloading {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as r, dest.open("wb") as out:
        out.write(r.read())
    got = _sha256(dest)
    if got != want_sha:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"checksum mismatch: want {want_sha}, got {got}")
    if platform.system() != "Windows":
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest

if __name__ == "__main__":
    print(ensure_fastchess())
```

### `.gitignore` entry

Add `tools/.cache/` to `.gitignore` (already pattern-aligned with existing `.gitignore` conventions per CLAUDE.md gitignore section).

## 7. V6 UCI Binary — Verification

[VERIFIED in code: `src/chess_engine/engine/v6/CMakeLists.txt` lines 39-49]

### V6 status

- V6's CMakeLists.txt defines **only** the `v6_engine` pybind11 module (`pybind11_add_module(v6_engine MODULE ${V6_SOURCES})`).
- No `add_executable(v6_uci ...)` target.
- No `src/uci_main.cpp` analog exists under `src/chess_engine/engine/v6/src/`.
- V6 is invoked from Python via the `v6_engine.chess_algorithm` adapter (pybind11). No process-level UCI surface.

**This is a planner-blocking gap for V7-vs-V6 SPRT (and for V6-vs-V6 sanity).** fastchess requires a process to spawn — it does not embed Python or load `.pyd`/`.so` modules.

### V7 status

[VERIFIED in code: `src/chess_engine/engine/v7/CMakeLists.txt` line 112-130 + `src/uci_main.cpp`]

- `v7_uci` standalone executable target exists (Phase 1 FOUND-07).
- Implements: `uci`, `isready`, `ucinewgame`, `position`, `go`, `stop`, `quit`.
- **Silently ignores unknown commands including `setoption`** (lines 207-210: "Phase 1: unknown commands silently ignored (no setoption / debug / register).").
- `go` parses `depth N` and `movetime MS` only; `wtime`/`btime`/`winc`/`binc`/`movestogo` are ignored (line 184 comment).

### Planner-required gap-closure (must precede first gauntlet run)

The plan MUST include these as prerequisite tasks before the harness can actually drive V6 vs V7:

1. **Add `v6_uci` CMake target.** Mirror the `v7_uci` block in V6's CMakeLists.txt. Write `src/chess_engine/engine/v6/src/uci_main.cpp` modeled on `v7_uci`'s loop (~210 lines). This is the highest-risk prerequisite — touches V6's CMake (must not break the pybind11 module build) and adds a new C++ source file under V6.

2. **Extend `v7_uci` (and the new `v6_uci`) to accept `setoption`.** Even if it just accepts + ignores them, fastchess sends `setoption name Hash value 64` etc. on every match and may complain if the engine doesn't respond. Minimum viable: parse `setoption name X value Y` tokens, no-op silently, never print an error. Ideal: actually apply `Hash` (resize TT) and `Threads` (no-op for Phase 2 since both engines are single-threaded).

3. **Extend `go` to parse `wtime`/`btime`/`winc`/`binc`.** fastchess uses TC `10+0.1` → sends `go wtime 10000 btime 10000 winc 100 binc 100`. v7_uci currently ignores these and falls back to `DEFAULT_GO_TIME_MS = 5000`. **This causes a silent every-move 5-second cap regardless of the time control flag.** Without this fix, V7 will play at the wrong TC and the gauntlet results are meaningless. Time management: budget ~ `(my_time / 30) + my_inc` as a Phase-2-scope simple heuristic; SRCH-15 (10% safety margin) is Phase 1's responsibility.

These three sub-items belong inside the Phase 2 plan, not as a separate gap-closure plan — they are the table stakes for the harness to be able to validate anything.

## 8. NPS Extraction Strategy

### Option A: parse from PGN (recommended)

[VERIFIED: fastchess `-pgnout` accepts `nodes=true` and `nps=true` per man.md] When `-pgnout nodes=true nps=true` is set, fastchess annotates each move with the engine-reported `nps=`. The gauntlet runner reads the PGN after fastchess exits, groups by engine name, computes median + mean. Pros: zero extra subprocess work; per-game NPS distributions are visible in the data; aligns with already-emitted artifact (D-06 says PGN is already an output). Cons: median across all moves is dominated by short games' opening-book moves where NPS is artificial.

### Option B: dedicated bench run per gauntlet (cleaner signal)

Have `tools/gauntlet.py` run a separate `v7_uci bench` / `v6_uci bench` on a fixed position (e.g., Kiwipete at depth 8 or fixed-time 1s) BEFORE the SPRT match starts. Record those two single-position NPS values in `summary.json.nps`. Pros: clean apples-to-apples NPS comparison on the same position with no opening-book noise; matches what Phase 1's `test_nps_sentinel` already measures (single-position). Cons: requires `v7_uci` (and `v6_uci`) to support a `bench` UCI extension OR requires a fixed `position fen ... go movetime 1000` then parse `info` lines' `nps`.

### Recommendation: **Option B**, hybrid with A as fallback

Run a fixed-position movetime probe (`position fen <Kiwipete>; go movetime 1000; stop`) for each engine immediately after the harness build, parse the last `info ... nps N ...` line, record in `summary.json.nps.{engine}.bench_nps`. Also compute Option A's per-move median from the PGN for cross-check. The pytest sentinel (D-13) reads `bench_nps` specifically:

```python
v7_nps = summary["nps"]["v7"]["bench_nps"]
v6_nps = summary["nps"]["v6"]["bench_nps"]
assert v7_nps >= 0.8 * v6_nps, f"V7 NPS regression: {v7_nps} vs V6 {v6_nps}"
```

This matches the structure of the existing Phase 1 `test_nps_sentinel(v7_native_engine)` test ([VERIFIED in `tests/test_v7_engine.py:118`]), just sourcing the numbers from `summary.json` instead of running the search inline.

**Note:** the v7_uci already has time-control-driven mode; the bench-probe is just `position startpos; go movetime 1000` followed by polling its stdout for `info ... nps`. No engine-side changes needed beyond the `setoption`/`wtime` extensions in §7.

## 9. Validation Architecture

> Nyquist validation is enabled (`workflow.nyquist_validation: true` in `.planning/config.json`). This section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already configured under `[dependency-groups].dev` in `pyproject.toml`) |
| Config file | none — pytest discovers `tests/test_*.py` via default rules |
| Quick run command | `python3 -m uv run --group dev pytest tests/test_gauntlet.py -q` |
| Full suite command | `python3 -m uv run --group dev pytest -q` |
| Benchmark-gated NPS sentinel | `RUN_BENCHMARKS=1 python3 -m uv run --group dev pytest tests/test_gauntlet.py::test_nps_regression -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| GAUNT-01 | `fetch_fastchess.py` idempotent + checksum-verifies | unit | `pytest tests/test_fetch_fastchess.py::test_idempotent_when_cached -x` | ❌ Wave 0 |
| GAUNT-01 | OS routing returns correct asset for current platform | unit | `pytest tests/test_fetch_fastchess.py::test_asset_for_host -x` | ❌ Wave 0 |
| GAUNT-01 | Bad SHA256 raises and removes the cached file | unit | `pytest tests/test_fetch_fastchess.py::test_checksum_mismatch_raises -x` | ❌ Wave 0 |
| GAUNT-02 | `v7_uci` accepts `setoption name Hash value N` without error | unit (subprocess) | `pytest tests/test_uci_binaries.py::test_v7_uci_setoption -x` | ❌ Wave 0 |
| GAUNT-02 | `v6_uci` exists, responds `uciok`, plays one move from startpos | unit (subprocess) | `pytest tests/test_uci_binaries.py::test_v6_uci_smoke -x` | ❌ Wave 0 |
| GAUNT-02 | `v7_uci` parses `go wtime`/`btime` and respects TC | unit (subprocess) | `pytest tests/test_uci_binaries.py::test_v7_uci_wtime_btime -x` | ❌ Wave 0 |
| GAUNT-03 | `summary.json.fastchess_command` is a literal re-runnable list | unit | `pytest tests/test_gauntlet.py::test_command_persisted -x` | ❌ Wave 0 |
| GAUNT-03 | Same engine + same opening + same seed produces same result | integration (slow) | manual: re-run V6-vs-V6 twice, diff `summary.json.result` | manual |
| GAUNT-04 | V6-vs-V6 over 200 games yields Elo in [-15, +15] | integration (slow, ~30-60 min) | `pytest tests/test_gauntlet.py::test_v6_sanity -m slow` (skipped by default) | ❌ Wave 0 — must run on Phase 1-verified host |
| GAUNT-05 | `8moves_v3.pgn` is reachable from `gauntlet.py` (file exists, valid PGN) | unit | `pytest tests/test_gauntlet.py::test_book_present -x` | ❌ Wave 0 |
| GAUNT-06 | Pentanomial SPRT bounds are passed to fastchess literally as `elo0=0 elo1=10 alpha=0.05 beta=0.05` | unit | `pytest tests/test_gauntlet.py::test_sprt_flags_hardcoded -x` | ❌ Wave 0 |
| GAUNT-07 | PGN with `[Termination "time forfeit"]` is tallied into `summary.json.result.time_forfeits` | unit (fixture PGN) | `pytest tests/test_gauntlet.py::test_time_forfeit_parse -x` | ❌ Wave 0 |
| GAUNT-08 | Pytest sentinel fails when `v7_bench_nps < 0.8 * v6_bench_nps` | unit (synthetic summary.json) | `pytest tests/test_gauntlet.py::test_nps_regression -x` | ❌ Wave 0 |
| GAUNT-08 | Sentinel reads the LATEST `summary.json` under `.planning/gauntlets/` | unit | `pytest tests/test_gauntlet.py::test_latest_summary -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_gauntlet.py tests/test_fetch_fastchess.py tests/test_uci_binaries.py -q` — unit tests only, ~seconds. Skips the slow V6-vs-V6 sanity run.
- **Per wave merge:** Full pytest suite `python3 -m uv run --group dev pytest -q` to ensure no V1-V6 regression (INT-08 invariant from Phase 1) and no test file collision.
- **Phase gate:** Run `RUN_BENCHMARKS=1` + the slow V6-vs-V6 sanity gauntlet end-to-end ON A HOST WITH PHASE 1 VERIFIED. Then `pytest -q -m slow` confirms `test_v6_sanity` passes (Elo in [-15, +15]). This is GAUNT-04 itself.

### Wave 0 Gaps

- [ ] `tests/test_fetch_fastchess.py` — new file; covers GAUNT-01 sub-cases (idempotency, checksum, OS routing)
- [ ] `tests/test_uci_binaries.py` — new file; covers GAUNT-02 sub-cases for both v6_uci and v7_uci as subprocess (uci/isready handshake, setoption, position+go+bestmove)
- [ ] `tests/test_gauntlet.py` — new file; covers all `gauntlet.py` parsing/orchestration logic + the NPS sentinel (D-13). Marker `slow` for the actual SPRT run that GAUNT-04 requires.
- [ ] `tests/fixtures/sample_fastchess_output.txt` — captured stdout block (Elo/SPRT/LLR/Games/Penta lines) for parser unit tests
- [ ] `tests/fixtures/sample_games.pgn` — small fixture PGN with one `[Termination "time forfeit"]` entry to validate time-forfeit parsing
- [ ] `conftest.py` shared fixture for spinning up a v7_uci subprocess on a temp directory (planner discretion: per-file or shared)

### Validation guardrails

- **Do NOT run the slow V6-vs-V6 sanity (GAUNT-04) in CI by default** — 30-60 min wall clock at 10+0.1 c=1 will burn CI budget. Gate behind an explicit `RUN_SLOW_GAUNTLET=1` env var or pytest marker `-m slow` (not run by default).
- **Do NOT run any V7 gauntlet in CI** — Phase 1 perf bugs make NPS measurements meaningless until gap-closure (D-09). Document this in the test docstrings so the deferral reasoning is visible at the failure site.
- **The NPS sentinel (`test_nps_regression`)** must read from a synthetic `summary.json` fixture during unit testing, NOT trigger a real gauntlet. The real check happens when a human/CI runs the full `RUN_BENCHMARKS=1` sentinel after the V7-vs-V6 run completes.

## 10. Open Questions for Planner

### Cannot resolve from docs alone (verify during implementation)

1. **Exact `[Termination]` string for time forfeits in fastchess PGN.** [ASSUMED based on cutechess compatibility] cutechess emits `[Termination "time forfeit"]`; fastchess inherits this convention but the exact string was not confirmed in docs. The planner should write a contrived test (engine that sleeps past TC) early in implementation and capture the actual string. The time-forfeit parsing logic depends on this.

2. **Exact fastchess release asset filenames at the chosen tag.** [VERIFIED that releases exist; ASSUMED about per-tag naming consistency] Disservin/fastchess release asset naming has evolved across versions (some include `-musl`, ARM variants added later, etc.). The planner should run `curl ... /releases/latest` at plan time and pin to actual filenames, not pattern-match.

3. **License compatibility of `8moves_v3.pgn` from `official-stockfish/books`.** [ASSUMED] Stockfish itself is GPL-3.0; the books repo's LICENSE was not confirmed. If GPL, vendoring the PGN may require this repo to be GPL — confirm before committing. If incompatible, the fallback is fetch-at-runtime per D-11.

4. **Whether `v6_engine` exposes a TT-size setter via pybind11.** [PARTIAL: not searched exhaustively] If the C++ V6 engine has a `set_hash_size(N)` or equivalent on its Engine class, then `v6_uci` can implement `setoption name Hash value N` to apply it. If not, V6 will run with whatever default TT it has and the GAUNT-03 "identical Hash size" invariant becomes notional. The planner needs to grep V6's `python_bindings.cpp` early; if no setter exists, document it as a known asymmetry in the V6-vs-V6 sanity run (both V6 instances will use the same default, so sanity still works; V7-vs-V6 verdict will need an exposed setter or an asterisk).

5. **Whether `v7_uci`'s `Engine::stop()` actually interrupts mid-search in the unit-test subprocess context.** [VERIFIED to be a documented limitation in uci_main.cpp lines 200-204] The current loop reads stdin synchronously; `stop` doesn't fire until after search returns. For TC-based gauntlet matches this works because fastchess respects wtime/btime rather than sending mid-search `stop`. For `go infinite` it doesn't. Planner should not need to fix this for Phase 2 (TC-bounded only), but should call it out in the plan as a "Phase 4 concern when async search lands."

6. **Whether fastchess inherits cwd-relative paths or requires absolute paths for `-engine cmd=`.** Probably the latter (more portable) — but worth confirming in the first integration test. The wrapper should pass absolute paths defensively.

### Resolved by spec / existing decisions

- TC default → D-08 (`10+0.1`).
- Concurrency → D-08a (`1`).
- SPRT bounds → D-12 (hardcoded).
- V6-vs-V6 tolerance → D-10 (`[-15, +15]` Elo).
- NPS regression threshold → D-13 (`0.8 * v6_nps`).
- Artifact layout → D-06 (`.planning/gauntlets/{ISO-timestamp}/`).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | fastchess emits `[Termination "time forfeit"]` in PGN for time losses | §4, §10 Q1 | GAUNT-07 parser produces wrong counts; fixable by editing the string match after first observation |
| A2 | Per-release asset filenames follow `fastchess-{platform}-{arch}` convention | §3, §6 | Fetch URL 404s; trivial fix once correct filenames known |
| A3 | `8moves_v3.pgn` license permits in-repo vendoring | §5 | May need to switch to fetch-on-demand; structural impact on the plan |
| A4 | V6's pybind11 module exposes (or can trivially expose) a `set_hash_size`/equivalent | §10 Q4 | `v6_uci`'s `setoption Hash` becomes a no-op; V6-vs-V6 sanity still works because asymmetry is zero |
| A5 | fastchess `-recover` handles V7 perf-bug-induced timeouts gracefully (continues match) | §2 | Without `-recover`, a single timeout aborts the run; explicitly setting `-recover` mitigates |
| A6 | `bench` UCI extension or `position + go movetime + parse info` works in both v6_uci (once built) and v7_uci for NPS probing | §8 | Fall back to PGN-derived NPS (Option A) |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | `fetch_fastchess.py`, `gauntlet.py` | ✓ (project pin: 3.12) | declared in `.python-version` | — |
| uv | running pytest under group dev | ✓ (project assumes) | — | `pip install -e .[all]` |
| pytest | test suite | ✓ (`[dependency-groups].dev`) | — | — |
| C++17 + CMake ≥3.15 | building `v6_uci` (NEW), rebuilding `v7_uci` | ✗ on current dev host per `.continue-here.md` | — | Phase 2 requires a host with toolchain; same blocker as Phase 1 verification |
| fastchess binary | every gauntlet run | ✗ (not in repo by design — fetched on demand) | pinned in `fetch_fastchess.py` | none — runtime dependency |
| Built `v7_uci` | every gauntlet run | ⚠ source-complete (Phase 1) but unverified on current host | — | run Phase 1 deferred build gates first |
| Built `v6_uci` | every gauntlet run | ✗ **does not exist** — see §7 | — | none — must add to V6 CMakeLists.txt as a Phase 2 prereq task |
| Built `v6_engine` pybind11 module | (not needed by fastchess — only by GameManager) | ✓ source-complete | — | — |
| Network access (one-time, on first fetch) | `fetch_fastchess.py` | host-dependent | — | document offline-install procedure (drop pre-fetched binary at `tools/.cache/fastchess`) |

**Missing dependencies with no fallback:**
- `v6_uci` standalone executable — **MUST be added by Phase 2 plan as the first task** (see §7).

**Missing dependencies with fallback:**
- C++/CMake toolchain — Phase 1 verification deferral inherits to Phase 2; the planner should document that running the V6-vs-V6 sanity (GAUNT-04) requires a fully-toolchained host and is the same gate as Phase 1's deferred verification.

## Sources

### Primary (HIGH confidence)
- **fastchess official man.md** — https://github.com/Disservin/fastchess/blob/master/man.md — full CLI surface, SPRT flag syntax, `-pgnout` options
- **fastchess GitHub** — https://github.com/Disservin/fastchess — primary source, releases page
- **fastchess releases** — https://github.com/Disservin/fastchess/releases — pinned-version source
- **chessprogramming wiki — Fastchess** — https://www.chessprogramming.org/Fastchess_(Game_Manager) — canonical SPRT examples
- **chessprogramming wiki — SPRT** — https://www.chessprogramming.org/Sequential_Probability_Ratio_Test — theory + verdict logic
- **official-stockfish/books** — https://github.com/official-stockfish/books — canonical `8moves_v3.pgn` source
- **Phase 1 v7_uci source** — `src/chess_engine/engine/v7/src/uci_main.cpp` — verified setoption + wtime/btime gaps
- **V6 CMakeLists.txt** — `src/chess_engine/engine/v6/CMakeLists.txt` — verified no `v6_uci` target exists
- **Phase 1 NPS sentinel** — `tests/test_v7_engine.py::test_nps_sentinel` — verified D-13 structural template

### Secondary (MEDIUM confidence)
- **dogeystamp SPRT testing guide** — https://www.dogeystamp.com/chess3/ — verified fastchess stdout regex patterns
- **OpenChess fastchess guide** — https://open-chess.org/viewtopic.php?t=4360 — pentanomial example commands
- **ijccrl fastchess SPRT guide** — https://ijccrl.com/guide-of-fastchess-sprt-test/ — practical SPRT recipes
- **official-stockfish fishtest Running-Fastchess** — https://official-stockfish.github.io/docs/fishtest-wiki/Running-Fastchess.html — Stockfish dev's own usage pattern
- **fishtest games.py parser** — official-stockfish/fishtest `worker/games.py` — battle-tested reference for parsing fastchess output

### Tertiary (LOW confidence — flagged for in-implementation verification)
- Exact PGN `[Termination]` string for time forfeits (A1)
- Per-release fastchess asset naming convention (A2)
- `8moves_v3.pgn` license compatibility (A3)

## Metadata

**Confidence breakdown:**
- fastchess CLI surface: **HIGH** — multiple consistent authoritative sources, including the upstream man.md
- Output parsing: **HIGH** — dogeystamp + fishtest both document and demonstrate exact regex patterns; verdict logic is unambiguous
- Pinned release: **MEDIUM** — release page exists, but exact filenames + SHA256s require planner to query the releases API at plan time
- Opening book sourcing: **HIGH** — canonical source identified
- V6/V7 UCI binary status: **HIGH** — verified directly in repo source
- NPS extraction: **MEDIUM** — two viable paths both verifiable; recommendation hedged by fallback
- Time-forfeit parsing: **MEDIUM** — convention is well-known but exact string for fastchess specifically not confirmed in docs

**Research date:** 2026-05-16
**Valid until:** 2026-06-15 (fastchess is actively developed; release naming may shift)

## RESEARCH COMPLETE
