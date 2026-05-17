---
phase: 02-gauntlet-harness-early
plan: 04a
type: execute
wave: 2
depends_on: ["02-01", "02-02", "02-03"]
files_modified:
  - tools/gauntlet_core.py
  - tools/__init__.py
  - tests/test_gauntlet_core.py
  - tests/fixtures/sample_fastchess_output.txt
  - tests/fixtures/sample_games.pgn
autonomous: true
requirements:
  - GAUNT-03
  - GAUNT-06
  - GAUNT-07
user_setup: []

must_haves:
  truths:
    - "tools/gauntlet_core.py exposes pure functions only — no subprocess calls, no filesystem mutation, no network — so the parser/builder are testable offline"
    - "build_fastchess_command is a pure function that emits the literal CLI tokens per RESEARCH §2 with hardcoded SPRT params (D-12) and hardcoded concurrency=1 (D-08a)"
    - "parse_fastchess_stdout extracts the LAST progress block's Elo / LLR / Games / Penta via regex and computes the SPRT verdict from (llr, lower, upper)"
    - "parse_pgn_terminations matches the §10 Q1 RESOLVED TIME_FORFEIT_PATTERNS tuple (case-insensitive) AND over-flags unclassified non-normal terminations so any future fastchess string change cannot silently miscount"
    - "TIME_FORFEIT_PATTERNS is a module-level constant tuple containing at least 'time forfeit' and 'on time' per §10 Q1 RESOLVED"
  artifacts:
    - path: "tools/gauntlet_core.py"
      provides: "Pure helpers: constants, build_fastchess_command, parse_fastchess_stdout, parse_pgn_terminations, collect_per_move_nps, compute_sanity_verdict, GauntletError exception"
      contains: "TIME_FORFEIT_PATTERNS"
      min_lines: 150
    - path: "tests/test_gauntlet_core.py"
      provides: "Unit tests: command builder shape, SPRT-params-hardcoded, stdout regex parser, [Termination] tally + investigation_required edge cases"
      contains: "test_sprt_flags_hardcoded"
    - path: "tests/fixtures/sample_fastchess_output.txt"
      provides: "Captured fastchess stdout block (two progress blocks; last wins)"
    - path: "tests/fixtures/sample_games.pgn"
      provides: "Small fixture PGN: one normal game + one [Termination 'time forfeit'] + one mixed-case + one unclassified non-normal"
  key_links:
    - from: "tools/gauntlet_core.py"
      to: "RESEARCH §2 representative command"
      via: "build_fastchess_command emits the literal token sequence; hardcoded SPRT_ELO0/ELO1/ALPHA/BETA per D-12"
      pattern: "elo0=0"
    - from: "tools/gauntlet_core.py"
      to: "RESEARCH §10 Q1 RESOLVED contract"
      via: "TIME_FORFEIT_PATTERNS + over-flag fallback path setting investigation_required"
      pattern: "TIME_FORFEIT_PATTERNS"
---

<objective>
Split A of the former Plan 02-04: implement the pure-function half of the gauntlet runner — constants, command builder, stdout parser, PGN [Termination] parser, sanity-verdict computation. Zero side effects.

Purpose: WARNING-2 from the checker review found the original Plan 02-04 Task 1 too large (~10 functions + 250 LOC in a single auto task). Splitting into 02-04a (pure) and 02-04b (I/O) keeps each task within the context budget AND lets 02-04b's executor read 02-04a's contracts as-shipped before composing them. Also operationalizes BLOCKER-2 (D-09 deferral is enforced as `SystemExit(2)` in 02-04b, not a bypass flag) and WARNING-3 (the parser tallies forfeits; 02-04b's writer sets the investigation_required flag).

Output: tools/gauntlet_core.py with the pure helpers, plus the two test fixtures and a pure-function unit-test suite.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/02-gauntlet-harness-early/02-CONTEXT.md
@.planning/phases/02-gauntlet-harness-early/02-RESEARCH.md
@.planning/phases/02-gauntlet-harness-early/02-PATTERNS.md
@.planning/phases/02-gauntlet-harness-early/02-01-SUMMARY.md
@.planning/phases/02-gauntlet-harness-early/02-02-SUMMARY.md
@.planning/phases/02-gauntlet-harness-early/02-03-SUMMARY.md
@tools/fetch_fastchess.py
@tools/gen_coeffs.py
</context>

<interfaces>
<!-- Pure-function surface that 02-04b consumes: -->
<!--   DEFAULT_TC: str = "10+0.1"  (D-08) -->
<!--   CONCURRENCY: int = 1        (D-08a) -->
<!--   SPRT_ELO0: int = 0; SPRT_ELO1: int = 10; SPRT_ALPHA: float = 0.05; SPRT_BETA: float = 0.05  (D-12) -->
<!--   SANITY_TOLERANCE_ELO: int = 15  (D-10) -->
<!--   TIME_FORFEIT_PATTERNS: tuple[str, ...] = ("time forfeit", "on time")  (RESEARCH §10 Q1 RESOLVED) -->
<!--   OTHER_NONNORMAL_PATTERNS: tuple[str, ...] = ("adjudication", "adjudicated", "illegal move", "disconnected")  (over-flag bucket) -->
<!--   LINE_PATTERNS: dict[str, re.Pattern] keyed by "elo" / "llr" / "games" / "penta" -->
<!--   class GauntletError(RuntimeError): pass -->
<!-- Functions: -->
<!--   build_fastchess_command(*, fastchess_path, engines, tc, hash_mb, threads, run_dir, opening_book_path, rounds, sanity_mode) -> list[str] -->
<!--   parse_fastchess_stdout(text: str) -> dict  (keys: elo, elo_err, elo_ci, llr, llr_lower, llr_upper, games{n,w,l,d}, penta[5], verdict) -->
<!--   parse_pgn_terminations(pgn_path: Path, engine_names: list[str]) -> dict  (returns {"time_forfeits": dict, "other_terminations": dict, "investigation_required": bool}) -->
<!--   collect_per_move_nps(pgn_path: Path, engine_names: list[str]) -> dict[str, dict]  (per-engine median/mean/samples) -->
<!--   compute_sanity_verdict(elo: float) -> str  (returns "PASS" if abs(elo) <= SANITY_TOLERANCE_ELO else "FAIL"; boundary inclusive per D-10) -->
<!-- All functions take Path objects directly (parse_pgn_terminations + collect_per_move_nps); they read the file but produce no other I/O. -->
-->
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement tools/gauntlet_core.py with constants + pure helpers</name>
  <files>tools/gauntlet_core.py, tools/__init__.py</files>
  <read_first>
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §2 (CANONICAL fastchess command line — literal template for build_fastchess_command)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §4 (regex patterns, summary.json schema, per-game time-forfeit extraction)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §10 Q1 RESOLVED (TIME_FORFEIT_PATTERNS contract + over-flag fallback)
    - .planning/phases/02-gauntlet-harness-early/02-PATTERNS.md section "tools/gauntlet.py"
    - tools/gen_coeffs.py lines 108-131 (stdlib-only discipline + deterministic JSON shape)
  </read_first>
  <behavior>
    - Constants module-resolvable: TIME_FORFEIT_PATTERNS = ("time forfeit", "on time"); SPRT_ELO0=0; SPRT_ELO1=10; SPRT_ALPHA=0.05; SPRT_BETA=0.05; CONCURRENCY=1; SANITY_TOLERANCE_ELO=15
    - build_fastchess_command(sanity_mode=False, ...) returns list containing literal tokens "-sprt", "elo0=0", "elo1=10", "alpha=0.05", "beta=0.05"
    - build_fastchess_command(sanity_mode=True, ...) returns list containing NO "-sprt" token
    - build_fastchess_command output always contains "-concurrency" followed by "1"
    - build_fastchess_command output includes "-openings" followed by "file=<opening_book_path>" (path passed in by caller; this function does NOT resolve it)
    - parse_fastchess_stdout: given two progress blocks, returns the LATER one's values
    - parse_fastchess_stdout: when llr >= upper -> verdict == "H1"; when llr <= lower -> "H0"; otherwise "inconclusive"
    - parse_pgn_terminations: counts "time forfeit" + "on time" (case-insensitive); buckets adjudication/illegal/disconnected into other_terminations; sets investigation_required=true if any unclassified non-normal termination appears
    - parse_pgn_terminations: when a PGN has zero time forfeits AND zero unclassified terminations, investigation_required=false
    - compute_sanity_verdict(0.0) == "PASS"; compute_sanity_verdict(15.0) == "PASS"; compute_sanity_verdict(-15.0) == "PASS"; compute_sanity_verdict(15.01) == "FAIL"
  </behavior>
  <action>
    Create tools/gauntlet_core.py as a stdlib-only module exposing exactly the surface in <interfaces>. Stdlib imports: dataclasses, pathlib, re, statistics, typing. No subprocess, no urllib, no os.environ writes, no file writes.

    Constants block (verbatim values from D-08 / D-08a / D-09 / D-10 / D-12 / RESEARCH §2 / §10 Q1 RESOLVED):
      DEFAULT_TC = "10+0.1"  # D-08
      CONCURRENCY = 1  # D-08a
      SPRT_ELO0 = 0; SPRT_ELO1 = 10; SPRT_ALPHA = 0.05; SPRT_BETA = 0.05  # D-12
      SANITY_TOLERANCE_ELO = 15  # D-10
      TIME_FORFEIT_PATTERNS = ("time forfeit", "on time")  # §10 Q1 RESOLVED — case-insensitive substring
      OTHER_NONNORMAL_PATTERNS = ("adjudication", "adjudicated", "illegal move", "disconnected")  # §10 Q1 RESOLVED — over-flag bucket
      NORMAL_TERMINATIONS = ("normal", "")  # case-insensitive; absent header treated as "normal"
      LINE_PATTERNS = {  # RESEARCH §4
          "elo": re.compile(r"^Elo\s*\|\s*(-?\d+\.\d+)\s*\+-\s*(\d+\.\d+)\s*\((\d+)%\)", re.MULTILINE),
          "llr": re.compile(r"^LLR\s*\|\s*(-?\d+\.\d+)\s*\((-?\d+\.\d+),\s*(-?\d+\.\d+)\)\s*\[(-?\d+\.\d+),\s*(-?\d+\.\d+)\]", re.MULTILINE),
          "games": re.compile(r"^Games\s*\|\s*N:\s*(\d+)\s*W:\s*(\d+)\s*L:\s*(\d+)\s*D:\s*(\d+)", re.MULTILINE),
          "penta": re.compile(r"^Penta\s*\|\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]", re.MULTILINE),
      }
      BENCH_FEN = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"  # Kiwipete
      BENCH_MOVETIME_MS = 1000

    Exception:
      class GauntletError(RuntimeError):
          pass

    Function: build_fastchess_command(*, fastchess_path: Path, engines: dict[str, Path], tc: str, hash_mb: int, threads: int, run_dir: Path, opening_book_path: Path, rounds: int, sanity_mode: bool) -> list[str]
      - Emit tokens in stable order:
        [str(fastchess_path)]
        + for each (name, binary_path) in engines.items():
            ["-engine", f"cmd={binary_path}", f"name={name}", f"option.Hash={hash_mb}", f"option.Threads={threads}"]
        + ["-each", f"tc={tc}"]
        + ["-openings", f"file={opening_book_path}", "format=pgn", "order=random", "plies=16"]
        + ["-rounds", str(rounds), "-repeat", "-concurrency", str(CONCURRENCY), "-recover"]
        + (["-sprt", f"elo0={SPRT_ELO0}", f"elo1={SPRT_ELO1}", f"alpha={SPRT_ALPHA}", f"beta={SPRT_BETA}"] if not sanity_mode else [])
        + ["-report", "penta=true"]
        + ["-ratinginterval", "10", "-scoreinterval", "10"]
        + ["-pgnout", f"file={run_dir}/games.pgn", "notation=san", "nodes=true", "nps=true", "tbhits=true"]
        + ["-log", f"file={run_dir}/fastchess.log"]
        + ["-randomseed"]
      - Function MUST be pure: no side effects, no path resolution, no mkdir. Caller owns I/O.
      - Use the literal strings "elo0={SPRT_ELO0}" etc. so the grep gate in acceptance criteria sees "elo0=0".

    Function: parse_fastchess_stdout(text: str) -> dict
      - For each pattern in LINE_PATTERNS, find ALL matches via re.finditer and keep the LAST match's groups (the final progress block is authoritative per RESEARCH §4).
      - Build result dict with keys: elo (float), elo_err (float), elo_ci (int), llr (float), llr_lower (float), llr_upper (float), games (dict n/w/l/d as ints), penta (list of 5 ints).
      - Compute verdict: if llr >= llr_upper -> "H1"; elif llr <= llr_lower -> "H0"; else "inconclusive".
      - If the text lacks any required pattern (e.g. fastchess crashed before printing a progress block), set the corresponding values to None and verdict="inconclusive". Do NOT raise — let the caller decide.

    Function: parse_pgn_terminations(pgn_path: Path, engine_names: list[str]) -> dict
      - Walk the file line-by-line. State: current_white, current_black, current_termination per game (reset on each new [Event ...] or [Result ...]; simplest: reset on [White header).
      - Header regex: r'^\[(\w+)\s+"(.*)"\]$' applied to each non-blank line; capture (key, value).
      - At end of each game (detect via blank line or next [Event] / next [White]), classify the termination:
          - tlower = termination_value.lower()
          - if any(p in tlower for p in TIME_FORFEIT_PATTERNS): forfeit_engine = white if (depends on result — but for Phase 2 simpler: count against BOTH the white and black, then attribute to the loser via Result tag: "1-0" means Black forfeited if termination is time forfeit, "0-1" means White, "1/2-1/2" attribute to neither). Increment time_forfeits[loser_name].
          - elif any(p in tlower for p in OTHER_NONNORMAL_PATTERNS): increment other_terminations[loser_name].
          - elif tlower in NORMAL_TERMINATIONS or termination header absent: skip (normal completion).
          - else: this is the over-flag path — set investigation_required = True, increment time_forfeits[loser_name] defensively (better to over-count than miss), AND record the unrecognized string in a debug list (returned under key "unrecognized_terminations" for the writer to log).
      - Return dict: {"time_forfeits": {engine_name: count, ...}, "other_terminations": {engine_name: count, ...}, "investigation_required": bool, "unrecognized_terminations": list[str]}
      - All engine_names must appear as keys in both sub-dicts (default 0) even if no forfeits/terminations.

    Function: collect_per_move_nps(pgn_path: Path, engine_names: list[str]) -> dict
      - Walk pgn_path. For each move with a "{...}" comment, extract `nps=N` via re.search(r"nps=(\d+)").
      - Attribute to engine: track White/Black per game and ply parity (odd ply = White's move).
      - Group integers per engine; compute statistics.median and statistics.mean; record sample count.
      - Return dict {engine_name: {"median": int|None, "mean": float|None, "samples": int}} — None when zero samples.

    Function: compute_sanity_verdict(elo: float) -> str
      - Return "PASS" if abs(elo) <= SANITY_TOLERANCE_ELO else "FAIL". Boundary inclusive (D-10).

    tools/__init__.py: if absent, create empty file. If present (Plan 03 may have created it), leave untouched.

    NO subprocess, NO urllib, NO os.environ writes, NO file writes anywhere in this module. Plan 02-04b owns all I/O.
  </action>
  <verify>
    <automated>python3 -c "from tools.gauntlet_core import build_fastchess_command, parse_fastchess_stdout, parse_pgn_terminations, collect_per_move_nps, compute_sanity_verdict, GauntletError, TIME_FORFEIT_PATTERNS, SPRT_ELO0, SPRT_ELO1, SPRT_ALPHA, SPRT_BETA, CONCURRENCY, SANITY_TOLERANCE_ELO; print('OK', TIME_FORFEIT_PATTERNS, SPRT_ELO0, SPRT_ELO1, CONCURRENCY)" 2>&1 | tail -5</automated>
  </verify>
  <acceptance_criteria>
    - File exists: tools/gauntlet_core.py with at least 150 lines
    - `python3 -c "from tools.gauntlet_core import SPRT_ELO0, SPRT_ELO1, SPRT_ALPHA, SPRT_BETA; print(SPRT_ELO0, SPRT_ELO1, SPRT_ALPHA, SPRT_BETA)"` prints "0 10 0.05 0.05" (D-12 hardcoded)
    - `python3 -c "from tools.gauntlet_core import CONCURRENCY; print(CONCURRENCY)"` prints "1" (D-08a hardcoded)
    - `python3 -c "from tools.gauntlet_core import TIME_FORFEIT_PATTERNS; print('time forfeit' in TIME_FORFEIT_PATTERNS and 'on time' in TIME_FORFEIT_PATTERNS)"` prints "True" (§10 Q1 RESOLVED)
    - `grep -v '^[[:space:]]*#' tools/gauntlet_core.py | grep -c "elo0={SPRT_ELO0}" >= 1 || grep -v '^[[:space:]]*#' tools/gauntlet_core.py | grep -c "elo0=0" >= 1` — SPRT literal in command builder, satisfying D-12 grep gate
    - Module has zero subprocess/urllib/os.makedirs/Path.write_text/open(...,"w") usage (`grep -E "subprocess|urllib|makedirs|write_text|open\(.*['\"]w" tools/gauntlet_core.py | grep -v '^[[:space:]]*#' | wc -l` returns 0)
    - tools/__init__.py exists (empty file is fine)
  </acceptance_criteria>
  <done>tools/gauntlet_core.py provides the full pure-function surface for the gauntlet runner; zero side effects; 02-04b can import and compose these helpers.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Unit tests + fixtures — command builder, stdout parser, [Termination] tally, sanity verdict, investigation_required flag</name>
  <files>tests/test_gauntlet_core.py, tests/fixtures/sample_fastchess_output.txt, tests/fixtures/sample_games.pgn</files>
  <read_first>
    - tools/gauntlet_core.py (Task 1 output — read post-edit; tests assert against the actual constant names and function signatures)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §4 (literal Elo/SPRT/LLR/Games/Penta block — seed for sample_fastchess_output.txt)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §10 Q1 RESOLVED (TIME_FORFEIT_PATTERNS + over-flag fallback — drives the fixture PGN cases)
    - tests/test_v7_bindings.py (pytest idioms: tmp_path, parametrize)
  </read_first>
  <behavior>
    - test_sprt_flags_hardcoded: build_fastchess_command(sanity_mode=False, ...) returns list containing "-sprt", "elo0=0", "elo1=10", "alpha=0.05", "beta=0.05"
    - test_sanity_mode_omits_sprt: build_fastchess_command(sanity_mode=True, ...) returns NO "-sprt" token
    - test_concurrency_always_one: every build_fastchess_command output contains "-concurrency" "1"
    - test_default_tc_is_10_plus_0_1: build_fastchess_command(tc="10+0.1", ...) contains "-each" then "tc=10+0.1"
    - test_opening_book_path_passed_through: build_fastchess_command(opening_book_path=Path("/some/book.pgn"), ...) contains "file=/some/book.pgn"
    - test_parse_fastchess_stdout_extracts_last_block: fixture has two blocks; parser returns the LATER block's values
    - test_verdict_h1_on_high_llr: synthetic text with llr above upper -> verdict == "H1"
    - test_verdict_h0_on_low_llr: synthetic text with llr below lower -> verdict == "H0"
    - test_verdict_inconclusive_in_between: returns "inconclusive"
    - test_verdict_inconclusive_on_missing_data: empty stdout returns verdict == "inconclusive" without raising
    - test_time_forfeit_parse_lowercase: fixture with [Termination "time forfeit"] is counted as a forfeit
    - test_time_forfeit_parse_on_time: fixture with [Termination "on time"] is counted as a forfeit (§10 Q1 RESOLVED)
    - test_time_forfeit_case_insensitive: fixture with [Termination "Time Forfeit"] is counted
    - test_other_termination_buckets_separately: [Termination "adjudication"] increments other_terminations, NOT time_forfeits
    - test_unrecognized_termination_triggers_investigation: fixture with [Termination "weird new string"] sets investigation_required=true AND records the string in unrecognized_terminations
    - test_no_forfeits_no_investigation: fixture with only [Termination "normal"] entries returns investigation_required=false
    - test_engine_names_default_to_zero: parse_pgn_terminations(..., engine_names=["v6", "v7"]) returns both keys even when no games involve them
    - test_sanity_verdict_boundary_inclusive: compute_sanity_verdict(15.0) == "PASS"; compute_sanity_verdict(-15.0) == "PASS"; compute_sanity_verdict(15.01) == "FAIL"; compute_sanity_verdict(0.0) == "PASS"
  </behavior>
  <action>
    Three sub-artifacts:

    A. tests/fixtures/sample_fastchess_output.txt — seed with at least TWO complete progress blocks (RESEARCH §4 format). Use realistic numbers; the SECOND block must have different Elo / LLR / Games / Penta values than the first so test_parse_fastchess_stdout_extracts_last_block can meaningfully assert "last wins". Example: block 1 with Elo 10.2, LLR 1.5, Games N:2000; block 2 with Elo 13.87, LLR 2.90, Games N:4186. The test asserts the parser returns block 2's values.

    B. tests/fixtures/sample_games.pgn — small fixture with at least 5 games covering each parse path:
      - Game 1: [White "v7"] [Black "v6"] [Result "1-0"] [Termination "normal"] — normal completion
      - Game 2: [White "v6"] [Black "v7"] [Result "1-0"] [Termination "time forfeit"] — Black (v7) forfeited on time
      - Game 3: [White "v7"] [Black "v6"] [Result "0-1"] [Termination "Time Forfeit"] — mixed case; White (v7) forfeited
      - Game 4: [White "v7"] [Black "v6"] [Result "0-1"] [Termination "on time"] — alternate forfeit phrase
      - Game 5: [White "v6"] [Black "v7"] [Result "1/2-1/2"] [Termination "adjudication"] — bucketed to other_terminations
      - Game 6: [White "v7"] [Black "v6"] [Result "0-1"] [Termination "weird new string"] — over-flag path → investigation_required=true
      Include a few `nps=N` annotations in move comments on a couple games so test_collect_per_move_nps would work (defer the actual test to 02-04b if it requires file resolution; pure parser tests are fine here).
      Keep the file under 100 lines.

    C. tests/test_gauntlet_core.py — implement all behaviors from <behavior>. Import as `from tools import gauntlet_core as gc`.
      - Use pytest's tmp_path / parametrize as needed.
      - For build_fastchess_command tests: pass synthetic Path objects (do not need to exist on disk).
      - For parse_fastchess_stdout verdict tests: synthesize a minimal stdout string with just the LLR pattern at chosen values.
      - For parse_pgn_terminations tests: use the shipped tests/fixtures/sample_games.pgn (one canonical fixture for all PGN tests).
      - For test_unrecognized_termination_triggers_investigation: assert returned dict has investigation_required == True AND "weird new string" in unrecognized_terminations list.
      - For test_no_forfeits_no_investigation: build a tiny ad-hoc PGN in tmp_path containing only [Termination "normal"] games; assert investigation_required == False.
      - Total runtime budget: < 3 s (all pure unit, no subprocess).
  </action>
  <verify>
    <automated>python3 -m uv run --group dev pytest -q tests/test_gauntlet_core.py -x 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - Three files exist: tests/test_gauntlet_core.py, tests/fixtures/sample_fastchess_output.txt, tests/fixtures/sample_games.pgn
    - tests/fixtures/ directory exists (created by this task)
    - `grep -c "def test_" tests/test_gauntlet_core.py` returns at least 18
    - All tests PASS — no test requires any external binary
    - Total test runtime ≤ 3 s
    - `grep -F "elo0=0" tests/test_gauntlet_core.py | wc -l` ≥ 1 — D-12 hardcoding asserted by tests, not just code
    - `grep -F "investigation_required" tests/test_gauntlet_core.py | wc -l` ≥ 2 — investigation_required behavior is asserted both true and false
    - sample_games.pgn contains at least one of each: "time forfeit", "Time Forfeit", "on time", "adjudication", "weird new string", "normal" (`grep -c '\[Termination ' tests/fixtures/sample_games.pgn >= 5`)
  </acceptance_criteria>
  <done>18+ unit tests pass; fixtures committed; the pure-function half of the gauntlet runner is fully tested offline.</done>
</task>

</tasks>

<verification>
- `python3 -m uv run --group dev pytest -q tests/test_gauntlet_core.py` passes
- tools/gauntlet_core.py is pure (no subprocess/urllib/file-write)
- No regression in other test files
</verification>

<success_criteria>
- tools/gauntlet_core.py committed with the full pure-function surface
- 18+ unit tests pass offline
- TIME_FORFEIT_PATTERNS exported and operationalized per §10 Q1 RESOLVED
- investigation_required computed correctly for normal / forfeit / unrecognized cases
</success_criteria>

<output>
After completion, create `.planning/phases/02-gauntlet-harness-early/02-04a-SUMMARY.md` recording: exact TIME_FORFEIT_PATTERNS tuple shipped, sample_games.pgn contents (game count + termination strings used), test pass count, and a note that 02-04b's I/O closure depends on these contracts unchanged.
</output>
