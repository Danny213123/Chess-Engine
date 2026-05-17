---
phase: 02-gauntlet-harness-early
plan: 04b
type: execute
wave: 3
depends_on: ["02-04a"]
files_modified:
  - tools/gauntlet.py
  - tests/test_gauntlet_io.py
autonomous: true
requirements:
  - GAUNT-03
  - GAUNT-06
  - GAUNT-07
user_setup: []

must_haves:
  truths:
    - "tools/gauntlet.py is the user-facing CLI; it composes tools/gauntlet_core helpers with the I/O surfaces (subprocess + filesystem + git rev-parse)"
    - "Every gauntlet run produces .planning/gauntlets/<ISO-timestamp>/ with three artifacts: games.pgn, summary.json, fastchess.log (D-06)"
    - "summary.json contains schema_version, timestamp_utc, engines{label:{cmd,git_sha,options}}, tc, concurrency, openings, sprt (or null in sanity), fastchess_command, fastchess_version, host, result{verdict, elo, llr, games, penta, time_forfeits, other_terminations, investigation_required}, nps{label:{bench_nps,median,mean,samples}}"
    - "When sum(time_forfeits.values()) > 0 OR parse_pgn_terminations returned investigation_required=true, write_summary sets summary['result']['investigation_required']=true AND prints '⚠ N time forfeit(s) — investigate before trusting result' to stderr"
    - "tools/gauntlet.py run subcommand exits with code 2 and the literal message 'V7-vs-V6 SPRT is deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2' — NO bypass flag exists"
    - "tools/gauntlet.py sanity subcommand drives a real V6-vs-V6 match end-to-end and writes summary.json"
    - "resolve_opening_book() returns either tools/books/8moves_v3.pgn (if vendored) OR fetches via tools/books/.fetch_fallback.json manifest to tools/.cache/8moves_v3.pgn (§10 Q3 RESOLVED Path B) — caller-transparent"
    - "resolve_engines returns absolute Path objects (§10 Q6 RESOLVED — fastchess wants absolute paths)"
  artifacts:
    - path: "tools/gauntlet.py"
      provides: "argparse subcommands run+sanity; resolve_engines; resolve_opening_book; run_bench_nps; run_fastchess; make_run_dir; write_summary; main"
      contains: "deferred to Phase 3"
      min_lines: 180
    - path: "tests/test_gauntlet_io.py"
      provides: "Unit tests for argparse wiring (D-09 hard deferral, sanity args), write_summary investigation_required flag, make_run_dir ISO format, resolve_opening_book fallback paths"
      contains: "test_run_subcommand_deferred"
  key_links:
    - from: "tools/gauntlet.py"
      to: "tools/gauntlet_core.py"
      via: "from tools.gauntlet_core import build_fastchess_command, parse_fastchess_stdout, parse_pgn_terminations, compute_sanity_verdict, GauntletError, TIME_FORFEIT_PATTERNS, SANITY_TOLERANCE_ELO, BENCH_FEN, BENCH_MOVETIME_MS"
      pattern: "from tools.gauntlet_core"
    - from: "tools/gauntlet.py"
      to: "tools/.cache/fastchess"
      via: "from tools.fetch_fastchess import ensure_fastchess; binary = ensure_fastchess()"
      pattern: "ensure_fastchess"
    - from: "tools/gauntlet.py"
      to: ".planning/gauntlets/<ISO>/summary.json"
      via: "json.dump indent=2 sort_keys=True ensure_ascii=False"
      pattern: "summary.json"
    - from: "tools/gauntlet.py"
      to: "tools/books/.fetch_fallback.json"
      via: "resolve_opening_book() reads manifest when 8moves_v3.pgn is absent; downloads to tools/.cache/8moves_v3.pgn with SHA256 gate"
      pattern: ".fetch_fallback.json"
---

<objective>
Split B of the former Plan 02-04: implement the I/O half of the gauntlet runner — subprocess orchestration, filesystem writes, argparse dispatch, summary.json writer. Composes the pure helpers from 02-04a.

Purpose: BLOCKER-2 (the D-09 deferral was being undermined by a `--i-know` bypass flag; this plan hard-enforces SystemExit(2) with no escape hatch). WARNING-3 (investigation_required flag must actually fire). WARNING-5 (license-conditional fetch-fallback for the opening book). WARNING-2 (the split that lets each task fit within context budget). The CLI is the only entry point a user calls; the pure half (02-04a) is what 02-05's tests import for fixtures.

Output: tools/gauntlet.py + an I/O-focused unit-test suite (filesystem + argparse paths only — parser/builder tests live in 02-04a).
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
@.planning/phases/02-gauntlet-harness-early/02-04a-SUMMARY.md
@tools/fetch_fastchess.py
@tools/gauntlet_core.py
@src/chess_engine/engine/v7/native_build.py
@tests/test_v7_bindings.py
</context>

<interfaces>
<!-- 02-04a's public surface (read-only contract — do not modify gauntlet_core.py from this plan): -->
<!--   from tools.gauntlet_core import ( -->
<!--     build_fastchess_command, parse_fastchess_stdout, parse_pgn_terminations, -->
<!--     collect_per_move_nps, compute_sanity_verdict, -->
<!--     GauntletError, -->
<!--     TIME_FORFEIT_PATTERNS, SPRT_ELO0, SPRT_ELO1, SPRT_ALPHA, SPRT_BETA, -->
<!--     CONCURRENCY, SANITY_TOLERANCE_ELO, DEFAULT_TC, -->
<!--     BENCH_FEN, BENCH_MOVETIME_MS, -->
<!--   ) -->

<!-- D-09 HARD DEFERRAL CONTRACT (BLOCKER-2): -->
<!--   `gauntlet.py run` exits with code 2 and prints to stderr exactly: -->
<!--     "V7-vs-V6 SPRT is deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2" -->
<!--   NO --i-know flag. NO escape hatch. The run subcommand parser still exists (so `--help` lists it), but invoking it always fails. -->

<!-- INVESTIGATION_REQUIRED CONTRACT (WARNING-3): -->
<!--   write_summary computes `forfeit_total = sum(time_forfeits.values())`. -->
<!--   If forfeit_total > 0 OR pgn_parse_result["investigation_required"] is True: -->
<!--     summary["result"]["investigation_required"] = True -->
<!--     print to stderr: f"⚠ {forfeit_total} time forfeit(s) — investigate before trusting result" -->
<!--   Else: summary["result"]["investigation_required"] = False -->
<!--   Plan 02-05 Task 3 (V6-vs-V6 sanity checkpoint) consumes this flag. -->

<!-- OPENING-BOOK RESOLVER (WARNING-5, §10 Q3 RESOLVED Path A/B): -->
<!--   def resolve_opening_book() -> Path: -->
<!--     vendored = Path("tools/books/8moves_v3.pgn").resolve() -->
<!--     if vendored.exists(): return vendored -->
<!--     manifest_path = Path("tools/books/.fetch_fallback.json") -->
<!--     if not manifest_path.exists(): raise GauntletError("no opening book and no fetch_fallback manifest") -->
<!--     manifest = json.loads(manifest_path.read_text()) -->
<!--     cache = Path("tools/.cache/8moves_v3.pgn") -->
<!--     if not cache.exists() or _sha256(cache) != manifest["sha256"]: -->
<!--       _download_with_sha_gate(manifest["url"], cache, manifest["sha256"]) -->
<!--     return cache.resolve() -->
-->
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement tools/gauntlet.py with argparse + I/O orchestration + D-09 hard deferral + investigation_required wiring + opening-book fallback resolver</name>
  <files>tools/gauntlet.py</files>
  <read_first>
    - tools/gauntlet_core.py (02-04a output — read post-edit; this module imports its public surface)
    - tools/fetch_fastchess.py (Plan 03 output — pattern for _sha256 + _download + atomic-write discipline; resolve_opening_book mirrors ensure_fastchess shape)
    - src/chess_engine/engine/v7/native_build.py lines 84-96 (canonical subprocess wrapper pattern; check=False, capture, surface tailed output on non-zero, domain-specific exception)
    - tools/gen_coeffs.py lines 108-131 (deterministic JSON write discipline; sorted keys, ensure_ascii=False, LF line endings)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §4 (summary.json schema — add investigation_required to result block)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §8 (NPS extraction Option B = bench probe before SPRT)
    - memory/project_phase1_known_perf_bugs.md (D-09 deferral rationale — required reading for the run-subcommand message)
  </read_first>
  <behavior>
    - `python3 tools/gauntlet.py run` exits with code 2 and stderr contains literal "V7-vs-V6 SPRT is deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"
    - `python3 tools/gauntlet.py run --help 2>&1` shows the run subcommand exists (so users discover it) but invoking it fails
    - `python3 tools/gauntlet.py sanity --games 0` exits non-zero with "must be > 0"
    - `python3 tools/gauntlet.py sanity --help` lists --games, --tc, --hash flags
    - resolve_opening_book() returns the vendored path when tools/books/8moves_v3.pgn exists
    - resolve_opening_book() falls back to manifest download when vendored path is absent AND tools/books/.fetch_fallback.json exists
    - resolve_opening_book() raises GauntletError when neither vendored nor manifest is present
    - write_summary with synthetic time_forfeits={v6:0, v7:0} sets investigation_required=False and prints NO stderr warning
    - write_summary with synthetic time_forfeits={v6:1, v7:0} sets investigation_required=True and prints stderr warning containing "1 time forfeit"
    - write_summary with time_forfeits={v6:0, v7:0} but pgn parse investigation_required=True still sets summary investigation_required=True (over-flag path)
    - make_run_dir creates directory whose name matches r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$"
  </behavior>
  <action>
    Create tools/gauntlet.py as a stdlib-only Python CLI orchestrating I/O around the pure helpers in tools/gauntlet_core.

    Top imports: argparse, datetime, hashlib, json, os, pathlib (Path), platform, re, statistics, subprocess, sys, urllib.request; plus `from tools.gauntlet_core import *` (or explicit list per <interfaces>) and `from tools.fetch_fastchess import ensure_fastchess`.

    Constants:
      OUTPUT_ROOT = Path(".planning/gauntlets")
      VENDORED_BOOK = Path("tools/books/8moves_v3.pgn")
      FALLBACK_MANIFEST = Path("tools/books/.fetch_fallback.json")
      CACHED_BOOK = Path("tools/.cache/8moves_v3.pgn")
      D9_MESSAGE = "V7-vs-V6 SPRT is deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"
      FORFEIT_WARNING_TEMPLATE = "⚠ {n} time forfeit(s) — investigate before trusting result"

    Functions (each single-purpose, kept short):

    1. resolve_engines() -> dict[str, Path]:
       - Discover v6_uci and v7_uci via the multi-candidate-dir search shared with tests (mirror tests/test_v7_bindings.py _find_v7_uci_binary, generalized to v6 as well).
       - Return absolute Paths via .resolve() (§10 Q6 RESOLVED — fastchess wants absolute).
       - Raise GauntletError listing candidate paths when missing.

    2. resolve_opening_book() -> Path:
       - VENDORED path (Plan 03 Path A): if VENDORED_BOOK.resolve().exists() return it.
       - FALLBACK path (Plan 03 Path B, §10 Q3 RESOLVED): if FALLBACK_MANIFEST.exists(), read JSON {"url": str, "sha256": str}.
         - if CACHED_BOOK exists AND _sha256(CACHED_BOOK) == manifest["sha256"]: return CACHED_BOOK.resolve().
         - else: mkdir parents=True; urllib.request.urlopen the URL; atomic write to CACHED_BOOK.with_suffix(".part") then rename; verify SHA256; if mismatch, unlink and raise GauntletError("opening-book checksum mismatch").
         - return CACHED_BOOK.resolve().
       - else: raise GauntletError("no opening book at tools/books/8moves_v3.pgn and no tools/books/.fetch_fallback.json manifest — Plan 02-03 may not have run").

    3. _sha256(path: Path) -> str: hashlib.sha256 over 64KB chunks (mirror tools/fetch_fastchess.py).

    4. run_bench_nps(uci_binary: Path) -> int:
       - subprocess.run([str(uci_binary)], input=f"position fen {BENCH_FEN}\\ngo movetime {BENCH_MOVETIME_MS}\\nquit\\n", text=True, capture_output=True, timeout=BENCH_MOVETIME_MS/1000 + 5)
       - Parse LAST `info ... nps N ...` line via re.findall(r"\\bnps\\s+(\\d+)", result.stdout).
       - Return int(last_match) or raise GauntletError("no nps info line from " + str(uci_binary)).

    5. make_run_dir(root: Path = OUTPUT_ROOT) -> Path:
       - ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H-%M-%SZ")  # colons replaced for Windows
       - d = root / ts
       - d.mkdir(parents=True, exist_ok=False)  # exist_ok=False so duplicate timestamps raise
       - return d

    6. run_fastchess(command: list[str], log_path: Path) -> str:
       - subprocess.run(command, check=False, capture_output=True, text=True)  # SPRT can be hours; no timeout
       - On non-zero exit: log_path.write_text(result.stderr); raise GauntletError(f"fastchess exited {result.returncode}: {result.stderr[-500:]}")
       - On KeyboardInterrupt: re-raise after the caller's partial-summary write.
       - Return result.stdout.

    7. _git_sha() -> str:
       - Best-effort: subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()[:7] or "unknown" on any failure.

    8. write_summary(run_dir, *, command, engines, tc, sanity_mode, fastchess_version, bench_nps, parsed_result, pgn_parse_result, per_move_nps) -> Path:
       - Build summary dict per RESEARCH §4 schema. Key blocks:
         schema_version=1, timestamp_utc=datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00","Z"),
         engines={name: {"cmd": str(p), "git_sha": _git_sha(), "options": {"Hash": 64, "Threads": 1}} for name, p in engines.items()},
         tc=tc, concurrency=CONCURRENCY,
         openings={"file": str(resolve_opening_book()), "format": "pgn", "order": "random"},
         sprt=({"elo0": SPRT_ELO0, "elo1": SPRT_ELO1, "alpha": SPRT_ALPHA, "beta": SPRT_BETA} if not sanity_mode else None),
         fastchess_command=command,
         fastchess_version=fastchess_version,
         host={"os": platform.system(), "cpu": platform.processor(), "cores": os.cpu_count() or 1},
         result={...},  # see below
         nps={name: {"bench_nps": bench_nps.get(name), **per_move_nps.get(name, {})} for name in engines}
       - result block:
         time_forfeits = pgn_parse_result["time_forfeits"]
         other_terminations = pgn_parse_result["other_terminations"]
         forfeit_total = sum(time_forfeits.values())
         pgn_flag = pgn_parse_result.get("investigation_required", False)
         investigation_required = (forfeit_total > 0) or pgn_flag
         verdict = compute_sanity_verdict(parsed_result.get("elo", 0.0)) if sanity_mode else parsed_result.get("verdict", "inconclusive")
         result = {
           "verdict": verdict,
           "elo": parsed_result.get("elo"), "elo_err": parsed_result.get("elo_err"), "elo_ci": parsed_result.get("elo_ci"),
           "llr": parsed_result.get("llr"), "llr_lower": parsed_result.get("llr_lower"), "llr_upper": parsed_result.get("llr_upper"),
           "games": parsed_result.get("games"),
           "penta": parsed_result.get("penta"),
           "time_forfeits": time_forfeits,
           "other_terminations": other_terminations,
           "investigation_required": investigation_required,
         }
       - WARNING-3 SIDE EFFECT: if investigation_required: print(FORFEIT_WARNING_TEMPLATE.format(n=forfeit_total), file=sys.stderr).
       - Write (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\\n")
       - Return the summary.json path.

    9. _run_subcommand_deferred(args) -> int:
       - BLOCKER-2 enforcement: print(D9_MESSAGE, file=sys.stderr); return 2. No --i-know. No fallback path. No conditionals.

    10. _sanity_subcommand(args) -> int:
        - if args.games <= 0: print("--games must be > 0", file=sys.stderr); return 2.
        - fastchess_path = ensure_fastchess()
        - engines_resolved = resolve_engines()  # {"v6": path, "v7": path}
        - For sanity, both labels point at v6_uci: engines_for_sanity = {"v6_white": engines_resolved["v6"], "v6_black": engines_resolved["v6"]}
        - run_dir = make_run_dir(OUTPUT_ROOT)
        - bench_nps = {name: run_bench_nps(p) for name, p in engines_for_sanity.items()}
        - opening_book = resolve_opening_book()
        - command = build_fastchess_command(fastchess_path=fastchess_path, engines=engines_for_sanity, tc=args.tc, hash_mb=args.hash, threads=1, run_dir=run_dir, opening_book_path=opening_book, rounds=max(1, args.games // 2), sanity_mode=True)
        - try:
            stdout = run_fastchess(command, run_dir / "fastchess.log")
          except KeyboardInterrupt:
            parsed = {"verdict": "interrupted"}
            pgn_parse = {"time_forfeits": {n:0 for n in engines_for_sanity}, "other_terminations": {n:0 for n in engines_for_sanity}, "investigation_required": True, "unrecognized_terminations": []}
            write_summary(run_dir, command=command, engines=engines_for_sanity, tc=args.tc, sanity_mode=True, fastchess_version=_fastchess_version(fastchess_path), bench_nps=bench_nps, parsed_result=parsed, pgn_parse_result=pgn_parse, per_move_nps={})
            raise
        - parsed_result = parse_fastchess_stdout(stdout)
        - pgn_parse_result = parse_pgn_terminations(run_dir / "games.pgn", list(engines_for_sanity.keys()))
        - per_move_nps = collect_per_move_nps(run_dir / "games.pgn", list(engines_for_sanity.keys()))
        - summary_path = write_summary(...)
        - print(str(run_dir))  # stdout for downstream tooling
        - return 0

    11. _fastchess_version(fastchess_path) -> str:
        - subprocess.run([str(fastchess_path), "--version"], capture_output=True, text=True, check=False, timeout=10).stdout.strip().split("\\n")[0] or "unknown"

    12. main(argv) -> int:
        - argparse with subparsers: "run" (no flags needed — always fails) and "sanity" (--games int default 200, --tc default DEFAULT_TC, --hash int default 64).
        - Dispatch to _run_subcommand_deferred or _sanity_subcommand.
        - Wrap top-level in try/except GauntletError: print to stderr, return 1.

    if __name__ == "__main__": sys.exit(main(sys.argv[1:]))

    Use ONLY stdlib + tools.gauntlet_core + tools.fetch_fastchess. No third-party deps. No new pyproject entries.
  </action>
  <verify>
    <automated>python3 tools/gauntlet.py run 2>&1 | grep -F "deferred to Phase 3 (D-09)" && echo "RC=$?" && python3 -c "from tools import gauntlet; print(gauntlet.D9_MESSAGE)" 2>&1 | tail -3</automated>
  </verify>
  <acceptance_criteria>
    - File exists: tools/gauntlet.py with at least 180 lines
    - `python3 tools/gauntlet.py run; echo $?` prints "2" on the last line (D-09 hard deferral — BLOCKER-2 fix)
    - `python3 tools/gauntlet.py run 2>&1 1>/dev/null | grep -cF "deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"` returns 1
    - `grep -cF -- "--i-know" tools/gauntlet.py` returns 0 (no bypass flag exists — BLOCKER-2 verification)
    - `python3 tools/gauntlet.py sanity --games 0 2>&1; echo $?` exits non-zero with a "must be > 0" message
    - `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "ensure_fastchess()" >= 1`
    - `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "from tools.gauntlet_core import" >= 1` (composes pure helpers)
    - `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "investigation_required" >= 3` (WARNING-3: flag is computed, set on dict, and gated for stderr print)
    - `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c ".fetch_fallback.json" >= 1` (WARNING-5: fallback manifest path consumed)
    - `grep -v '^[[:space:]]*#' tools/gauntlet.py | grep -c "resolve_opening_book" >= 2` (function defined + called)
    - All public symbols import: `python3 -c "from tools.gauntlet import resolve_engines, resolve_opening_book, run_bench_nps, run_fastchess, make_run_dir, write_summary, main, D9_MESSAGE, FORFEIT_WARNING_TEMPLATE"` succeeds
  </acceptance_criteria>
  <done>tools/gauntlet.py exposes the run+sanity CLI with hard D-09 deferral, investigation_required wiring, and opening-book fallback resolver.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: tests/test_gauntlet_io.py — D-09 deferral, investigation_required flag, opening-book resolver fallback, make_run_dir ISO format</name>
  <files>tests/test_gauntlet_io.py</files>
  <read_first>
    - tools/gauntlet.py (Task 1 output — read post-edit; tests assert against actual constant names and function signatures)
    - tools/gauntlet_core.py (02-04a output — fixtures may call compute_sanity_verdict / parse_pgn_terminations directly when needed)
    - tests/test_v7_bindings.py (pytest idioms: tmp_path, monkeypatch, capsys)
    - .planning/phases/02-gauntlet-harness-early/02-RESEARCH.md §10 Q1 RESOLVED + §10 Q3 RESOLVED (drives the fallback-resolver tests)
  </read_first>
  <behavior>
    - test_run_subcommand_deferred: main(["run"]) returns 2; capsys.readouterr().err contains "deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"
    - test_run_subcommand_has_no_i_know_flag: ArgumentParser for run subcommand does NOT accept --i-know; main(["run", "--i-know"]) returns nonzero exit (argparse error 2) and capsys.readouterr().err contains "unrecognized arguments" or similar argparse error string
    - test_sanity_subcommand_rejects_zero_games: main(["sanity", "--games", "0"]) returns nonzero with "must be > 0"
    - test_sanity_subcommand_rejects_negative_games: main(["sanity", "--games", "-5"]) returns nonzero
    - test_write_summary_sets_investigation_required_on_forfeit: invoke write_summary with synthetic pgn_parse_result containing time_forfeits={"v6": 1, "v7": 0}; assert resulting summary.json's result.investigation_required == True AND stderr contains "1 time forfeit"
    - test_write_summary_no_investigation_when_clean: time_forfeits={"v6":0,"v7":0}, pgn investigation_required=False -> result.investigation_required == False; stderr does NOT contain "time forfeit"
    - test_write_summary_investigation_propagates_from_pgn_parse: time_forfeits all 0 but pgn_parse_result["investigation_required"]=True (over-flag path from gauntlet_core) -> result.investigation_required == True
    - test_write_summary_schema_keys: result dict written by write_summary contains all keys: verdict, elo, elo_err, elo_ci, llr, llr_lower, llr_upper, games, penta, time_forfeits, other_terminations, investigation_required
    - test_make_run_dir_iso_format: make_run_dir(tmp_path) returns a Path whose name matches r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z$" (Windows-safe, no colons)
    - test_make_run_dir_collision_raises: calling make_run_dir twice with monkeypatched datetime returning the same timestamp raises FileExistsError
    - test_resolve_opening_book_vendored: with tools/books/8moves_v3.pgn present (monkeypatch a tmp_path tree), function returns that path
    - test_resolve_opening_book_fallback_manifest: vendored book absent, manifest present (monkeypatched download); function returns cached path
    - test_resolve_opening_book_missing_both_raises: vendored absent, manifest absent -> GauntletError
    - test_resolve_opening_book_checksum_mismatch_raises: manifest present, download produces wrong bytes -> GauntletError with "checksum mismatch"; cached partial file cleaned up
  </behavior>
  <action>
    Create tests/test_gauntlet_io.py focused on the I/O paths only — parser/builder tests live in tests/test_gauntlet_core.py from 02-04a.

    - Import: `from tools import gauntlet as g`; `from tools import gauntlet_core as gc`.
    - Use pytest fixtures: tmp_path (for OUTPUT_ROOT monkeypatching), monkeypatch (for VENDORED_BOOK / FALLBACK_MANIFEST / CACHED_BOOK / urllib.request.urlopen), capsys (for stderr assertions on the D-09 message and forfeit warning).
    - For the D-09 message tests: assert the EXACT D9_MESSAGE string appears in stderr (not paraphrased).
    - For the investigation_required tests: build a synthetic engines dict (paths don't need to exist on disk — they're written into summary.json as strings), pass synthetic parsed_result (from RESEARCH §4 example values), and a synthetic pgn_parse_result that matches the gauntlet_core.parse_pgn_terminations return shape. Read the written summary.json back via json.load and assert on result.investigation_required.
    - For test_resolve_opening_book_fallback_manifest: monkeypatch g.VENDORED_BOOK to a tmp_path that doesn't exist; create g.FALLBACK_MANIFEST as a tmp JSON {"url": "http://fake", "sha256": "<sha of the bytes the monkeypatched urlopen returns>"}; monkeypatch urllib.request.urlopen to return a BytesIO with deterministic bytes; assert resolve_opening_book() returns the cached path.
    - For test_resolve_opening_book_checksum_mismatch_raises: same as above but manifest sha256 doesn't match the bytes; assert GauntletError raised, assert no leftover .part file.
    - For make_run_dir collision test: monkeypatch datetime.datetime.now to return a fixed value (or use a fake datetime class); call twice, assert FileExistsError on second call.
    - Test runtime budget: < 5 s (all unit; no real subprocess except the early-exit path tests that don't reach subprocess.run).
  </action>
  <verify>
    <automated>python3 -m uv run --group dev pytest -q tests/test_gauntlet_io.py -x 2>&1 | tail -20</automated>
  </verify>
  <acceptance_criteria>
    - File exists: tests/test_gauntlet_io.py
    - `grep -c "def test_" tests/test_gauntlet_io.py` returns at least 13
    - All tests PASS — no test requires fastchess, v6_uci, or v7_uci binaries
    - Total test runtime ≤ 5 s
    - `grep -F "deferred to Phase 3 (D-09)" tests/test_gauntlet_io.py | wc -l` ≥ 1 (BLOCKER-2 fix is asserted by tests)
    - `grep -c "investigation_required" tests/test_gauntlet_io.py` ≥ 3 (WARNING-3 behavior fully tested)
    - `grep -c ".fetch_fallback.json" tests/test_gauntlet_io.py` ≥ 1 (WARNING-5 fallback path tested)
    - Combined with 02-04a's tests: total test count for the gauntlet runner ≥ 31 (18 + 13)
  </acceptance_criteria>
  <done>13+ I/O unit tests pass; D-09 hard-deferral, investigation_required wiring, and opening-book fallback are fully exercised offline.</done>
</task>

</tasks>

<verification>
- `python3 -m uv run --group dev pytest -q tests/test_gauntlet_io.py` passes
- `python3 tools/gauntlet.py run; echo $?` prints 2 (D-09 hard deferral enforced)
- `grep -F -- "--i-know" tools/gauntlet.py` returns no matches (no bypass flag)
- `python3 tools/gauntlet.py sanity --games 4` (with built v6_uci + cached fastchess) produces a .planning/gauntlets/<ISO>/ directory with three artifacts and a summary.json whose result.investigation_required is correctly set
- No regression in other test files
</verification>

<success_criteria>
- tools/gauntlet.py + tests/test_gauntlet_io.py committed
- 13+ I/O unit tests pass offline
- D-09 hard deferral with literal message — no bypass flag (BLOCKER-2 fix)
- investigation_required flag fires on any forfeit and on over-flag PGN cases (WARNING-3 fix)
- resolve_opening_book handles both vendored and fetch-fallback paths (WARNING-5 fix)
</success_criteria>

<output>
After completion, create `.planning/phases/02-gauntlet-harness-early/02-04b-SUMMARY.md` recording: subcommands implemented (run deferred, sanity functional), confirmation D9_MESSAGE matches exactly, investigation_required behavior verified on synthetic forfeit + clean + over-flag cases, opening-book resolver path tested (vendored OR fallback), test pass count, and any deviations from RESEARCH §2 command flags.
</output>
