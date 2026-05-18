#!/usr/bin/env python3
"""I/O half of the Phase 2 gauntlet harness (Plan 02-04b).

This module is the user-facing CLI. It composes the pure helpers from
``tools.gauntlet_core`` with the I/O surfaces a gauntlet run needs:

* subprocess orchestration (``fastchess``, the per-engine bench probe,
  best-effort ``git rev-parse``),
* filesystem (``.planning/gauntlets/<ISO>/`` run-dir creation; deterministic
  ``summary.json`` writer; opening-book resolver with fetch-fallback),
* ``argparse`` dispatch for the two subcommands the harness exposes.

The two subcommands:

* ``run``     — V7-vs-V6 SPRT. **HARD DEFERRED to Phase 3 (D-09 / BLOCKER-2).**
                Always exits with code 2 and prints :data:`D9_MESSAGE`. The
                subcommand exists so ``--help`` lists it (users discover it
                via the parser), but invoking it never succeeds. There is
                NO bypass flag of any kind and no environment-variable
                opt-out — the gate is intentionally absolute per BLOCKER-2.
* ``sanity``  — V6-vs-V6 sanity run end-to-end (drives fastchess, writes
                the three D-06 artifacts, computes the ``compute_sanity_verdict``
                PASS/FAIL).

The ``investigation_required`` flag (WARNING-3) is computed in :func:`write_summary`:
any time-forfeit count > 0 OR a truthy ``investigation_required`` from
:func:`tools.gauntlet_core.parse_pgn_terminations` (the over-flag bucket for
unrecognized non-normal ``[Termination]`` strings) flips the summary's
``result.investigation_required`` to True AND emits a stderr warning. Plan
02-05 Task 3's sanity-checkpoint acceptance consumes this flag.

The opening-book resolver (:func:`resolve_opening_book`, WARNING-5 / §10 Q3
RESOLVED Path A/B) is caller-transparent: it returns the vendored
``tools/books/8moves_v3.pgn`` when present, otherwise downloads via the
``tools/books/.fetch_fallback.json`` manifest into ``tools/.cache/`` and
returns the cached path after a SHA256 gate (mirroring the
:func:`tools.fetch_fastchess.ensure_fastchess` discipline). Raises
:class:`tools.gauntlet_core.GauntletError` when neither path is available.

Stdlib only — no third-party deps. Imports
``tools.gauntlet_core`` (Plan 02-04a) and ``tools.fetch_fastchess`` (Plan 02-03).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import statistics  # noqa: F401  # exported for tests / future per-bench stats
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from tools.fetch_fastchess import ensure_fastchess
from tools.gauntlet_core import (
    BENCH_FEN,
    BENCH_MOVETIME_MS,
    CONCURRENCY,
    DEFAULT_TC,
    GauntletError,
    SPRT_ALPHA,
    SPRT_BETA,
    SPRT_ELO0,
    SPRT_ELO1,
    SANITY_TOLERANCE_ELO,  # noqa: F401  # documented re-export for downstream
    TIME_FORFEIT_PATTERNS,  # noqa: F401  # documented re-export for downstream
    build_fastchess_command,
    collect_per_move_nps,
    compute_sanity_verdict,
    parse_engine_options,
    parse_fastchess_stdout,
    parse_pgn_terminations,
)

# ---------------------------------------------------------------------------
# Constants — paths and contract-literal strings
# ---------------------------------------------------------------------------

#: Root under which each gauntlet run gets its own ISO-timestamp directory (D-06).
OUTPUT_ROOT: Path = Path(".planning/gauntlets")

#: Vendored opening-book location (Plan 02-03 Path A).
VENDORED_BOOK: Path = Path("tools/books/8moves_v3.pgn")

#: Fetch-fallback manifest (Plan 02-03 Path B, §10 Q3 RESOLVED).
FALLBACK_MANIFEST: Path = Path("tools/books/.fetch_fallback.json")

#: Cached download target for the fetch-fallback path.
CACHED_BOOK: Path = Path("tools/.cache/8moves_v3.pgn")

#: BLOCKER-2 — D-09 hard-deferral literal message. The string is asserted
#: verbatim by both :mod:`tests.test_gauntlet_io` and the Plan 02-05 sanity
#: checkpoint. NEVER paraphrase without coordinating with both tests AND
#: the verifier's grep gate.
D9_MESSAGE: str = "V7-vs-V6 SPRT is deferred to Phase 3 (D-09); harness ships V6-vs-V6 sanity only in Phase 2"

#: WARNING-3 — stderr template flipped by :func:`write_summary` when the
#: investigation_required flag fires. ``{n}`` is the total forfeit count.
FORFEIT_WARNING_TEMPLATE: str = (
    "⚠ {n} time forfeit(s) — investigate before trusting result"
)

#: Streaming SHA256 read size (matches :mod:`tools.fetch_fastchess`).
_CHUNK_SIZE: int = 1 << 16

#: Regex pulling the LAST ``nps N`` integer out of a UCI ``info`` line.
_NPS_RE: re.Pattern = re.compile(r"\bnps\s+(\d+)")


# ---------------------------------------------------------------------------
# Engine + opening-book discovery
# ---------------------------------------------------------------------------


def _candidate_uci_paths(engine_name: str) -> List[Path]:
    """Return the candidate-directory search list for ``<engine>_uci``.

    Mirrors ``tests/test_v7_bindings.py::_find_v7_uci_binary`` and
    ``tests/test_uci_binaries_v6.py::_find_v6_uci_binary`` — single-config
    (build root) and multi-config (Release/RelWithDebInfo/Debug) generators
    both produce launchable binaries.
    """
    engine_dir = Path("src/chess_engine/engine") / engine_name
    build_dir = engine_dir / "build"
    candidate_dirs = (
        build_dir / "Release",
        build_dir / "RelWithDebInfo",
        build_dir / "Debug",
        build_dir,
        engine_dir,
    )
    names = (f"{engine_name}_uci.exe", f"{engine_name}_uci")
    out: List[Path] = []
    for directory in candidate_dirs:
        for name in names:
            out.append(directory / name)
    return out


def resolve_engines() -> Dict[str, Path]:
    """Locate the v6_uci and v7_uci binaries; return absolute Paths.

    fastchess wants absolute paths (§10 Q6 RESOLVED) — the returned values
    are always ``Path.resolve()``-d so the ``-engine cmd=...`` argv survives
    a cwd change inside fastchess.
    """
    found: Dict[str, Path] = {}
    missing_lookups: Dict[str, List[Path]] = {}
    for name in ("v6", "v7"):
        candidates = _candidate_uci_paths(name)
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                found[name] = candidate.resolve()
                break
        else:
            missing_lookups[name] = candidates
    if missing_lookups:
        details = "\n".join(
            f"  {name}: tried {[str(p) for p in paths]}"
            for name, paths in missing_lookups.items()
        )
        raise GauntletError(
            "missing UCI binary/binaries — build with the V6/V7 CMake "
            "targets first:\n" + details
        )
    return found


def _sha256(path: Path) -> str:
    """Stream a SHA256 over ``path`` in 64 KiB chunks (constant memory).

    Mirrors :func:`tools.fetch_fastchess._sha256` so the resolver's trust
    gate is byte-for-byte identical to the fastchess fetch gate.
    """
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_opening_book() -> Path:
    """Return the absolute Path to the opening-book PGN (WARNING-5 / §10 Q3).

    Resolution order:

    1. **Vendored Path A** — if ``tools/books/8moves_v3.pgn`` exists, return
       it (no network, no manifest read).
    2. **Fallback Path B** — if ``tools/books/.fetch_fallback.json`` exists,
       read its ``{"url": str, "sha256": str}`` manifest. If a cached file
       already exists at ``tools/.cache/8moves_v3.pgn`` with a matching
       SHA256, return it. Otherwise atomically download the URL to a
       ``.part`` sibling, verify SHA256, rename on success, raise
       :class:`GauntletError` on mismatch (the corrupt ``.part`` is
       unlinked so the next run starts clean).
    3. **Neither present** — raise :class:`GauntletError` pointing at Plan
       02-03 as the provisioning owner.

    Mirrors :func:`tools.fetch_fastchess.ensure_fastchess`'s download
    discipline: atomic-rename + non-bypassable checksum gate.
    """
    vendored = VENDORED_BOOK.resolve()
    if vendored.exists():
        return vendored

    if not FALLBACK_MANIFEST.exists():
        raise GauntletError(
            f"no opening book at {VENDORED_BOOK} and no {FALLBACK_MANIFEST} "
            "manifest — Plan 02-03 may not have run"
        )

    manifest = json.loads(FALLBACK_MANIFEST.read_text(encoding="utf-8"))
    url = manifest["url"]
    want_sha = manifest["sha256"]

    cache = CACHED_BOOK
    if cache.exists() and _sha256(cache) == want_sha:
        return cache.resolve()

    cache.parent.mkdir(parents=True, exist_ok=True)
    part = cache.with_suffix(cache.suffix + ".part")
    try:
        with urllib.request.urlopen(url) as response, part.open("wb") as out:
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
    except Exception:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass
        raise

    got = _sha256(part)
    if got != want_sha:
        try:
            part.unlink()
        except OSError:
            pass
        raise GauntletError(
            f"opening-book checksum mismatch for {url} — "
            f"want {want_sha}, got {got}. Asset has been removed."
        )

    os.replace(part, cache)
    return cache.resolve()


# ---------------------------------------------------------------------------
# Subprocess wrappers
# ---------------------------------------------------------------------------


def run_bench_nps(uci_binary: Path) -> int:
    """Probe ``uci_binary`` with a 1 s movetime search at BENCH_FEN; return NPS.

    Sends ``position fen ... \\n go movetime ... \\n quit`` on stdin, parses
    the LAST ``nps N`` integer in the captured stdout, returns it. Raises
    :class:`GauntletError` when no ``nps`` line was found (e.g. the binary
    crashed before emitting one).

    Single-position, single-thread, no opening book — matches the Phase 1
    NPS-sentinel methodology (RESEARCH §8 Option B) so the D-13 sentinel
    can compare apples-to-apples across engines.
    """
    payload = (
        f"position fen {BENCH_FEN}\n"
        f"go movetime {BENCH_MOVETIME_MS}\n"
        "quit\n"
    )
    timeout = (BENCH_MOVETIME_MS / 1000.0) + 5.0
    result = subprocess.run(
        [str(uci_binary)],
        input=payload,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    matches = _NPS_RE.findall(result.stdout)
    if not matches:
        raise GauntletError(
            f"no `nps` info line from {uci_binary} — stderr tail: "
            f"{result.stderr[-500:]}"
        )
    return int(matches[-1])


def run_fastchess(command: List[str], log_path: Path) -> str:
    """Spawn fastchess and return its captured stdout.

    SPRT runs can be hours — NO timeout is imposed. On non-zero exit the
    captured stderr is written to ``log_path`` for post-mortem inspection
    and a :class:`GauntletError` is raised with the last 500 chars of
    stderr inlined. ``KeyboardInterrupt`` from inside ``subprocess.run``
    propagates naturally so the caller's partial-summary path can run.
    """
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(result.stderr or "", encoding="utf-8")
        except OSError:
            # Logging is best-effort; surface the real failure instead.
            pass
        raise GauntletError(
            f"fastchess exited {result.returncode}: "
            f"{(result.stderr or '')[-500:]}"
        )
    return result.stdout


def _git_sha() -> str:
    """Best-effort short HEAD SHA; returns ``'unknown'`` on any failure.

    Used only as a provenance breadcrumb inside ``summary.json.engines`` —
    failure (no git, detached, network repo) must not abort a gauntlet.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    sha = (result.stdout or "").strip()
    if not sha or result.returncode != 0:
        return "unknown"
    return sha[:7]


def _fastchess_version(fastchess_path: Path) -> str:
    """Best-effort version string from ``fastchess --version``.

    Returns ``'unknown'`` when the probe fails. Trimmed to the first line
    because some fastchess builds emit a banner.
    """
    try:
        result = subprocess.run(
            [str(fastchess_path), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    out = (result.stdout or "").strip()
    if not out:
        return "unknown"
    return out.splitlines()[0]


# ---------------------------------------------------------------------------
# Run-dir + summary writer
# ---------------------------------------------------------------------------


def make_run_dir(root: Path = OUTPUT_ROOT) -> Path:
    """Create ``<root>/<ISO-Z-no-colons>/``; return the new Path.

    The format ``%Y-%m-%dT%H-%M-%SZ`` replaces colons with hyphens so the
    path is valid on Windows (NTFS forbids ``:`` in filenames). The mkdir
    uses ``exist_ok=False`` so a duplicate-timestamp invocation raises
    :class:`FileExistsError` instead of silently sharing a run dir.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = root / ts
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _iso_now() -> str:
    """ISO 8601 UTC timestamp with trailing ``Z`` (not ``+00:00``)."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def write_summary(
    run_dir: Path,
    *,
    command: List[str],
    engines: Dict[str, Path],
    tc: str,
    sanity_mode: bool,
    fastchess_version: str,
    bench_nps: Dict[str, Optional[int]],
    parsed_result: dict,
    pgn_parse_result: dict,
    per_move_nps: Dict[str, dict],
) -> Path:
    """Compose and write ``<run_dir>/summary.json``; return its Path.

    Schema follows RESEARCH §4 + the Plan 02-04b ``must_haves.truths``
    block. Two responsibilities beyond plain dict assembly:

    1. **WARNING-3 — investigation_required computation.** The flag fires
       when ``sum(time_forfeits.values()) > 0`` OR when the upstream
       :func:`parse_pgn_terminations` already flipped its own
       ``investigation_required`` (over-flag bucket). On True, a stderr
       warning matching :data:`FORFEIT_WARNING_TEMPLATE` is printed so an
       attended run surfaces the condition immediately and Plan 02-05's
       sanity gate refuses to auto-approve.
    2. **Deterministic write.** JSON is dumped with ``indent=2``,
       ``sort_keys=True``, ``ensure_ascii=False``, trailing newline. Matches
       the project's deterministic-write discipline so re-runs produce
       byte-identical files when inputs match.
    """
    time_forfeits = pgn_parse_result.get("time_forfeits", {name: 0 for name in engines})
    other_terminations = pgn_parse_result.get(
        "other_terminations", {name: 0 for name in engines}
    )
    forfeit_total = sum(time_forfeits.values())
    pgn_flag = bool(pgn_parse_result.get("investigation_required", False))
    investigation_required = (forfeit_total > 0) or pgn_flag

    if sanity_mode:
        elo_for_verdict = parsed_result.get("elo")
        if elo_for_verdict is None:
            verdict = "inconclusive"
        else:
            verdict = compute_sanity_verdict(float(elo_for_verdict))
    else:
        verdict = parsed_result.get("verdict", "inconclusive")

    result_block = {
        "verdict": verdict,
        "elo": parsed_result.get("elo"),
        "elo_err": parsed_result.get("elo_err"),
        "elo_ci": parsed_result.get("elo_ci"),
        "llr": parsed_result.get("llr"),
        "llr_lower": parsed_result.get("llr_lower"),
        "llr_upper": parsed_result.get("llr_upper"),
        "games": parsed_result.get("games"),
        "penta": parsed_result.get("penta"),
        "time_forfeits": time_forfeits,
        "other_terminations": other_terminations,
        "investigation_required": investigation_required,
    }

    git_sha = _git_sha()
    engines_block = {
        name: {
            "cmd": str(path),
            "git_sha": git_sha,
            "options": {"Hash": 64, "Threads": 1},
        }
        for name, path in engines.items()
    }

    try:
        openings_path = str(resolve_opening_book())
    except GauntletError:
        # The summary writer must not fail because the book vanished mid-run
        # — record the unresolved path so the run dir is still valid evidence.
        openings_path = str(VENDORED_BOOK)

    nps_block: Dict[str, dict] = {}
    for name in engines:
        per_move = per_move_nps.get(name, {})
        nps_block[name] = {
            "bench_nps": bench_nps.get(name),
            "median": per_move.get("median"),
            "mean": per_move.get("mean"),
            "samples": per_move.get("samples", 0),
        }

    summary = {
        "schema_version": 1,
        "timestamp_utc": _iso_now(),
        "engines": engines_block,
        "tc": tc,
        "concurrency": CONCURRENCY,
        "openings": {"file": openings_path, "format": "pgn", "order": "random"},
        "sprt": (
            None
            if sanity_mode
            else {
                "elo0": SPRT_ELO0,
                "elo1": SPRT_ELO1,
                "alpha": SPRT_ALPHA,
                "beta": SPRT_BETA,
            }
        ),
        "fastchess_command": command,
        "fastchess_version": fastchess_version,
        "host": {
            "os": platform.system(),
            "cpu": platform.processor(),
            "cores": os.cpu_count() or 1,
        },
        "result": result_block,
        "nps": nps_block,
    }

    if investigation_required:
        print(
            FORFEIT_WARNING_TEMPLATE.format(n=forfeit_total),
            file=sys.stderr,
        )

    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary_path


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _run_subcommand_deferred(args: argparse.Namespace) -> int:
    """D-09 deferral — narrowed by Plan 04-02 for the self-play case.

    Original BLOCKER-2 contract (Phase 2): always print :data:`D9_MESSAGE`
    and exit 2; no escape hatch. Phase 4 Plan 04-02 narrows this for the
    PAR-09 self-play V7-vs-V7 gauntlet, but the narrowing is gated by
    BOTH per-side option flags being supplied on the CLI — without them
    the two sides are indistinguishable and the defer must still fire.

    Lift conditions (ALL must hold):
      1. ``--binary-a`` and ``--binary-b`` both provided (same path = self-play)
      2. ``--engine-a-options`` AND ``--engine-b-options`` both provided
         (so the two sides actually differ — e.g. Threads=4 vs Threads=1)

    Anything else (no args; only --binary-a; per-side options missing for
    one side; V6-vs-V7 cross-binary case) still hits the D-09 message.

    The dispatcher returns the I/O-layer exit code from
    :func:`_run_self_play_subcommand` when the lift fires, else 2.
    """
    binary_a = getattr(args, "binary_a", None)
    binary_b = getattr(args, "binary_b", None)
    engine_a_options = getattr(args, "engine_a_options", None)
    engine_b_options = getattr(args, "engine_b_options", None)

    lift_fires = (
        binary_a is not None
        and binary_b is not None
        and engine_a_options is not None
        and engine_b_options is not None
    )
    if not lift_fires:
        print(D9_MESSAGE, file=sys.stderr)
        return 2

    return _run_self_play_subcommand(args)


def _run_self_play_subcommand(args: argparse.Namespace) -> int:
    """Plan 04-02 PAR-09 self-play V7-vs-V7 invocation (narrow D-09 lift).

    Behavior:
      * ``--dry-run`` (Task 1 acceptance criterion): construct the
        fastchess command using :func:`build_fastchess_command` with the
        per-side option lists, print the command (space-separated) to
        stdout, exit 0. No subprocess is spawned, no run dir is created.
      * Without ``--dry-run``: out of scope for Plan 04-02 (the build host
        runs the bash one-liner from .continue-here.md, which invokes the
        sanity orchestration of fastchess directly via this same command).
        Returns 2 with a hint pointing at the .continue-here.md recipe.

    The dry-run path is what tests/test_gauntlet_io.py exercises and what
    a developer uses to preview the constructed argv before kicking off
    the multi-hour SPRT.
    """
    try:
        engine_a_opts = parse_engine_options(args.engine_a_options)
    except ValueError as exc:
        print(
            f"[gauntlet] --engine-a-options {exc}",
            file=sys.stderr,
        )
        return 2
    try:
        engine_b_opts = parse_engine_options(args.engine_b_options)
    except ValueError as exc:
        print(
            f"[gauntlet] --engine-b-options {exc}",
            file=sys.stderr,
        )
        return 2

    binary_a = Path(args.binary_a)
    binary_b = Path(args.binary_b)

    # In dry-run we deliberately do NOT call ensure_fastchess() — the dev
    # host that's previewing the command may not have fastchess installed.
    # The placeholder path appears verbatim in the dry-run stdout so the
    # operator can see what would be invoked.
    fastchess_path = Path("tools/.cache/fastchess")
    # In dry-run we do NOT create a real run dir; the path is a placeholder
    # so the constructed argv has stable, recognizable tokens.
    run_dir = Path(args.output_dir) if args.output_dir else Path(".planning/gauntlets/dry-run")
    # In dry-run we do NOT resolve the opening book through the network
    # fallback; the vendored path appears verbatim in stdout.
    opening_book = Path(args.book)

    engines: Dict[str, Path] = {
        "engine_a": binary_a,
        "engine_b": binary_b,
    }
    rounds = max(1, args.games // 2)
    command = build_fastchess_command(
        fastchess_path=fastchess_path,
        engines=engines,
        tc=args.tc,
        hash_mb=args.hash,
        threads=1,  # base; per-side options override per-engine
        run_dir=run_dir,
        opening_book_path=opening_book,
        rounds=rounds,
        sanity_mode=False,  # SPRT mode for PAR-09
        engine_a_options=engine_a_opts,
        engine_b_options=engine_b_opts,
    )

    if args.dry_run:
        print(" ".join(command))
        return 0

    print(
        "[gauntlet] non-dry-run self-play execution is owned by the "
        ".planning/phases/04-lazy-smp-texel-tuning/.continue-here.md "
        "PAR-09 recipe — run that bash one-liner on a build host.",
        file=sys.stderr,
    )
    return 2


def _sanity_subcommand(args: argparse.Namespace) -> int:
    """End-to-end V6-vs-V6 sanity match (the only functional subcommand).

    Sequence: validate ``--games`` > 0; ensure fastchess; resolve engines;
    pin both colour slots to v6_uci; make a fresh run dir; run two bench
    probes for the NPS block; resolve the opening book; build the
    fastchess command; invoke fastchess (catching ``KeyboardInterrupt`` so
    a partial summary still lands); parse stdout + PGN; write summary;
    print the run-dir path on stdout for downstream tooling.
    """
    if args.games <= 0:
        print("--games must be > 0", file=sys.stderr)
        return 2

    fastchess_path = ensure_fastchess()
    engines_resolved = resolve_engines()
    engines_for_sanity: Dict[str, Path] = {
        "v6_white": engines_resolved["v6"],
        "v6_black": engines_resolved["v6"],
    }
    run_dir = make_run_dir(OUTPUT_ROOT)
    bench_nps: Dict[str, Optional[int]] = {}
    for name, binary in engines_for_sanity.items():
        try:
            bench_nps[name] = run_bench_nps(binary)
        except (GauntletError, subprocess.TimeoutExpired) as exc:
            print(
                f"[gauntlet] bench probe failed for {name}: {exc}",
                file=sys.stderr,
            )
            bench_nps[name] = None

    opening_book = resolve_opening_book()
    command = build_fastchess_command(
        fastchess_path=fastchess_path,
        engines=engines_for_sanity,
        tc=args.tc,
        hash_mb=args.hash,
        threads=1,
        run_dir=run_dir,
        opening_book_path=opening_book,
        rounds=max(1, args.games // 2),
        sanity_mode=True,
    )
    fc_version = _fastchess_version(fastchess_path)

    try:
        stdout = run_fastchess(command, run_dir / "fastchess.log")
    except KeyboardInterrupt:
        parsed = {"verdict": "interrupted"}
        pgn_parse = {
            "time_forfeits": {n: 0 for n in engines_for_sanity},
            "other_terminations": {n: 0 for n in engines_for_sanity},
            "investigation_required": True,
            "unrecognized_terminations": [],
        }
        write_summary(
            run_dir,
            command=command,
            engines=engines_for_sanity,
            tc=args.tc,
            sanity_mode=True,
            fastchess_version=fc_version,
            bench_nps=bench_nps,
            parsed_result=parsed,
            pgn_parse_result=pgn_parse,
            per_move_nps={},
        )
        raise

    parsed_result = parse_fastchess_stdout(stdout)
    pgn_parse_result = parse_pgn_terminations(
        run_dir / "games.pgn", list(engines_for_sanity.keys())
    )
    per_move_nps = collect_per_move_nps(
        run_dir / "games.pgn", list(engines_for_sanity.keys())
    )
    write_summary(
        run_dir,
        command=command,
        engines=engines_for_sanity,
        tc=args.tc,
        sanity_mode=True,
        fastchess_version=fc_version,
        bench_nps=bench_nps,
        parsed_result=parsed_result,
        pgn_parse_result=pgn_parse_result,
        per_move_nps=per_move_nps,
    )
    print(str(run_dir))
    return 0


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gauntlet",
        description=(
            "Phase 2 gauntlet harness — SPRT runner (deferred) + V6-vs-V6 "
            "sanity match."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # NOTE: The `run` subcommand's D-09 defer was originally absolute
    # (BLOCKER-2). Plan 04-02 narrows it for the PAR-09 self-play case:
    # the lift fires ONLY when --binary-a, --binary-b, --engine-a-options,
    # and --engine-b-options are ALL supplied — otherwise the defer still
    # triggers. A future flag that ALSO must be opt-in stays safe under
    # this gate as long as the four-arg conjunction guards it.
    run_parser = subparsers.add_parser(
        "run",
        help=(
            "V7-vs-V6 SPRT (DEFERRED) + Plan 04-02 PAR-09 self-play "
            "V7-vs-V7 (per-side options required for the narrow lift)."
        ),
    )
    run_parser.add_argument(
        "--binary-a",
        type=str,
        default=None,
        help="Path to engine A UCI binary (self-play: same path as --binary-b).",
    )
    run_parser.add_argument(
        "--binary-b",
        type=str,
        default=None,
        help="Path to engine B UCI binary (self-play: same path as --binary-a).",
    )
    run_parser.add_argument(
        "--engine-a-options",
        type=str,
        default=None,
        dest="engine_a_options",
        help=(
            "';'-separated per-side options for engine A "
            "(e.g. \"Threads=4;Hash=64\"). Required for the PAR-09 lift."
        ),
    )
    run_parser.add_argument(
        "--engine-b-options",
        type=str,
        default=None,
        dest="engine_b_options",
        help=(
            "';'-separated per-side options for engine B "
            "(e.g. \"Threads=1;Hash=64\"). Required for the PAR-09 lift."
        ),
    )
    run_parser.add_argument(
        "--games",
        type=int,
        default=1000,
        help="Total games (must be > 0). Defaults to 1000 per CONTEXT D-10.",
    )
    run_parser.add_argument(
        "--tc",
        type=str,
        default=DEFAULT_TC,
        help=f"Time control (fastchess syntax). Defaults to {DEFAULT_TC!r}.",
    )
    run_parser.add_argument(
        "--hash",
        type=int,
        default=64,
        help="Base Hash table size in MiB. Defaults to 64 (Phase 2 alignment).",
    )
    run_parser.add_argument(
        "--book",
        type=str,
        default=str(VENDORED_BOOK),
        help=f"Opening book PGN path. Defaults to {str(VENDORED_BOOK)!r}.",
    )
    run_parser.add_argument(
        "--concurrency",
        type=int,
        default=CONCURRENCY,
        help=(
            "fastchess --concurrency (D-08a hardcodes to 1; surfaced as a "
            "no-op flag for recipe readability)."
        ),
    )
    run_parser.add_argument(
        "--sprt-elo0",
        type=int,
        default=SPRT_ELO0,
        dest="sprt_elo0",
        help=f"SPRT lower bound (D-12 frozen at {SPRT_ELO0}).",
    )
    run_parser.add_argument(
        "--sprt-elo1",
        type=int,
        default=SPRT_ELO1,
        dest="sprt_elo1",
        help=f"SPRT upper bound (D-12 frozen at {SPRT_ELO1}).",
    )
    run_parser.add_argument(
        "--sprt-alpha",
        type=float,
        default=SPRT_ALPHA,
        dest="sprt_alpha",
        help=f"SPRT alpha (D-12 frozen at {SPRT_ALPHA}).",
    )
    run_parser.add_argument(
        "--sprt-beta",
        type=float,
        default=SPRT_BETA,
        dest="sprt_beta",
        help=f"SPRT beta (D-12 frozen at {SPRT_BETA}).",
    )
    run_parser.add_argument(
        "--pentanomial",
        action="store_true",
        default=True,
        help="Use pentanomial SPRT model (D-12 default; flag present for recipe readability).",
    )
    run_parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        dest="output_dir",
        help=(
            "Output directory for run artifacts "
            "(e.g. .planning/gauntlets/phase4-par09). Optional; dry-run prints "
            "the constructed argv without creating it."
        ),
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        default=False,
        help=(
            "Print the constructed fastchess command and exit 0 without "
            "spawning fastchess (preview path used by tests + the recipe)."
        ),
    )
    run_parser.set_defaults(func=_run_subcommand_deferred)

    sanity_parser = subparsers.add_parser(
        "sanity",
        help="V6-vs-V6 sanity match — writes .planning/gauntlets/<ISO>/.",
    )
    sanity_parser.add_argument(
        "--games",
        type=int,
        default=200,
        help="Total games (must be > 0). Defaults to 200.",
    )
    sanity_parser.add_argument(
        "--tc",
        type=str,
        default=DEFAULT_TC,
        help=f"Time control (fastchess syntax). Defaults to {DEFAULT_TC!r}.",
    )
    sanity_parser.add_argument(
        "--hash",
        type=int,
        default=64,
        help="Hash table size in MiB per engine. Defaults to 64.",
    )
    sanity_parser.set_defaults(func=_sanity_subcommand)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Top-level CLI entry point. Returns process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except GauntletError as exc:
        print(f"[gauntlet] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
