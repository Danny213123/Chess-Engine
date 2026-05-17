"""Pure-function half of the Phase 2 gauntlet harness.

This module exposes only stdlib-only, side-effect-free helpers used by the
gauntlet runner (Plan 02-04b). It owns:

* Hardcoded SPRT / TC / sanity constants (D-08, D-08a, D-10, D-12).
* The `TIME_FORFEIT_PATTERNS` contract resolved in RESEARCH §10 Q1.
* The literal fastchess command builder per RESEARCH §2.
* The fastchess-stdout regex parser per RESEARCH §4.
* The PGN ``[Termination]`` tally that drives the ``investigation_required``
  signal AND the per-engine per-move NPS aggregator (D-13 sentinel input).

Side-effect contract: this module never spawns processes, never opens
network connections, never mutates ``os.environ``, and never writes to
disk. Plan 02-04b composes these helpers into the actual runner / writer.

References:
  - RESEARCH §2 — CANONICAL fastchess command line (literal token order)
  - RESEARCH §4 — regex patterns, summary.json schema
  - RESEARCH §10 Q1 RESOLVED — TIME_FORFEIT_PATTERNS contract + over-flag bucket
  - D-08 / D-08a / D-10 / D-12 — frozen knobs (TC, concurrency, tolerance, SPRT)
"""

from __future__ import annotations

import re
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants (D-08 / D-08a / D-10 / D-12 / RESEARCH §2 / §10 Q1 RESOLVED)
# ---------------------------------------------------------------------------

DEFAULT_TC: str = "10+0.1"  # D-08 — shared time control for V7 vs V6
CONCURRENCY: int = 1  # D-08a — single game at a time (no cache contention)

# D-12 — hardcoded pentanomial SPRT bounds. NEVER read from CLI.
SPRT_ELO0: int = 0
SPRT_ELO1: int = 10
SPRT_ALPHA: float = 0.05
SPRT_BETA: float = 0.05

# D-10 — V6-vs-V6 sanity tolerance; boundary inclusive
SANITY_TOLERANCE_ELO: int = 15

# §10 Q1 RESOLVED — case-insensitive substring match against [Termination "..."]
TIME_FORFEIT_PATTERNS: Tuple[str, ...] = ("time forfeit", "on time")
# §10 Q1 RESOLVED — over-flag bucket: known non-normal but NOT a time forfeit
OTHER_NONNORMAL_PATTERNS: Tuple[str, ...] = (
    "adjudication",
    "adjudicated",
    "illegal move",
    "disconnected",
)
# Absent header treated as "normal"
NORMAL_TERMINATIONS: Tuple[str, ...] = ("normal", "")

# RESEARCH §4 — regex against fastchess stdout progress block; multiline so a
# stream of repeated blocks is scanned in one pass and the LAST match wins.
LINE_PATTERNS: Dict[str, re.Pattern] = {
    "elo": re.compile(
        r"^Elo\s*\|\s*(-?\d+\.\d+)\s*\+-\s*(\d+\.\d+)\s*\((\d+)%\)",
        re.MULTILINE,
    ),
    "llr": re.compile(
        r"^LLR\s*\|\s*(-?\d+\.\d+)\s*\((-?\d+\.\d+),\s*(-?\d+\.\d+)\)\s*\[(-?\d+\.\d+),\s*(-?\d+\.\d+)\]",
        re.MULTILINE,
    ),
    "games": re.compile(
        r"^Games\s*\|\s*N:\s*(\d+)\s*W:\s*(\d+)\s*L:\s*(\d+)\s*D:\s*(\d+)",
        re.MULTILINE,
    ),
    "penta": re.compile(
        r"^Penta\s*\|\s*\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]",
        re.MULTILINE,
    ),
}

# Bench position used by the runner (passed through, not used here)
BENCH_FEN: str = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
BENCH_MOVETIME_MS: int = 1000

# Header parser for PGN walking
_PGN_HEADER_RE = re.compile(r'^\[(\w+)\s+"(.*)"\]\s*$')
# Pull `nps=N` out of an arbitrary PGN comment payload
_NPS_RE = re.compile(r"nps=(\d+)")


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------


class GauntletError(RuntimeError):
    """Raised by gauntlet helpers on unrecoverable structural errors.

    Pure-function parsers in THIS module never raise on malformed input —
    they return ``None`` / sentinel values and let the caller decide. This
    type exists so Plan 02-04b's I/O layer can raise consistently.
    """


# ---------------------------------------------------------------------------
# Command builder (RESEARCH §2 literal token order)
# ---------------------------------------------------------------------------


def build_fastchess_command(
    *,
    fastchess_path: Path,
    engines: Dict[str, Path],
    tc: str,
    hash_mb: int,
    threads: int,
    run_dir: Path,
    opening_book_path: Path,
    rounds: int,
    sanity_mode: bool,
) -> List[str]:
    """Return the literal fastchess argv list per RESEARCH §2.

    Pure: no side effects, no path resolution, no mkdir. Caller owns I/O.

    Token order matters — downstream test grep gates pin on literal strings
    like ``elo0=0`` / ``-concurrency 1`` / ``-sprt``. Use f-strings that
    interpolate the SPRT_* constants so any future bound change is one
    line and the grep gate catches an accidental float drift.
    """
    cmd: List[str] = [str(fastchess_path)]

    # -engine blocks in caller's dict order (Python 3.7+ preserves insertion)
    for name, binary_path in engines.items():
        cmd.extend(
            [
                "-engine",
                f"cmd={binary_path}",
                f"name={name}",
                f"option.Hash={hash_mb}",
                f"option.Threads={threads}",
            ]
        )

    cmd.extend(["-each", f"tc={tc}"])
    cmd.extend(
        [
            "-openings",
            f"file={opening_book_path}",
            "format=pgn",
            "order=random",
            "plies=16",
        ]
    )
    cmd.extend(
        [
            "-rounds",
            str(rounds),
            "-repeat",
            "-concurrency",
            str(CONCURRENCY),
            "-recover",
        ]
    )

    if not sanity_mode:
        # D-12 — SPRT bounds hardcoded; NEVER user-overridable
        cmd.extend(
            [
                "-sprt",
                f"elo0={SPRT_ELO0}",
                f"elo1={SPRT_ELO1}",
                f"alpha={SPRT_ALPHA}",
                f"beta={SPRT_BETA}",
            ]
        )

    cmd.extend(["-report", "penta=true"])
    cmd.extend(["-ratinginterval", "10", "-scoreinterval", "10"])
    cmd.extend(
        [
            "-pgnout",
            f"file={run_dir}/games.pgn",
            "notation=san",
            "nodes=true",
            "nps=true",
            "tbhits=true",
        ]
    )
    cmd.extend(["-log", f"file={run_dir}/fastchess.log"])
    cmd.append("-randomseed")

    return cmd


# ---------------------------------------------------------------------------
# fastchess stdout parser (RESEARCH §4)
# ---------------------------------------------------------------------------


def _last_match(pat: re.Pattern, text: str):
    last = None
    for m in pat.finditer(text):
        last = m
    return last


def parse_fastchess_stdout(text: str) -> dict:
    """Extract the LAST progress block's stats + compute SPRT verdict.

    Returns a dict with keys: ``elo``, ``elo_err``, ``elo_ci``, ``llr``,
    ``llr_lower``, ``llr_upper``, ``games`` (dict n/w/l/d), ``penta``
    (list of 5 ints), ``verdict``.

    If any required pattern is missing (e.g. fastchess crashed before
    printing a progress block) the corresponding values are ``None`` and
    verdict is ``"inconclusive"``. NEVER raises — the caller decides
    whether a missing-block result is fatal.
    """
    elo_m = _last_match(LINE_PATTERNS["elo"], text)
    llr_m = _last_match(LINE_PATTERNS["llr"], text)
    games_m = _last_match(LINE_PATTERNS["games"], text)
    penta_m = _last_match(LINE_PATTERNS["penta"], text)

    elo = float(elo_m.group(1)) if elo_m else None
    elo_err = float(elo_m.group(2)) if elo_m else None
    elo_ci = int(elo_m.group(3)) if elo_m else None

    if llr_m:
        llr = float(llr_m.group(1))
        llr_lower = float(llr_m.group(4))
        llr_upper = float(llr_m.group(5))
    else:
        llr = llr_lower = llr_upper = None

    games = (
        {
            "n": int(games_m.group(1)),
            "w": int(games_m.group(2)),
            "l": int(games_m.group(3)),
            "d": int(games_m.group(4)),
        }
        if games_m
        else None
    )
    penta = [int(g) for g in penta_m.groups()] if penta_m else None

    if llr is None or llr_lower is None or llr_upper is None:
        verdict = "inconclusive"
    elif llr >= llr_upper:
        verdict = "H1"
    elif llr <= llr_lower:
        verdict = "H0"
    else:
        verdict = "inconclusive"

    return {
        "elo": elo,
        "elo_err": elo_err,
        "elo_ci": elo_ci,
        "llr": llr,
        "llr_lower": llr_lower,
        "llr_upper": llr_upper,
        "games": games,
        "penta": penta,
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# PGN [Termination] tally — RESEARCH §10 Q1 RESOLVED contract
# ---------------------------------------------------------------------------


def _loser_from_result(result: str, white: str, black: str) -> Optional[str]:
    """Return the engine name that LOST this game (or None for draw / unknown).

    For a time-forfeit, the side that LOST on time is the loser per the PGN
    `[Result]` header (1-0 → black lost; 0-1 → white lost). Draws (1/2-1/2)
    return None — the writer will count them under both engines defensively
    via the unrecognized-termination over-flag bucket if relevant.
    """
    if result == "1-0":
        return black
    if result == "0-1":
        return white
    return None


def parse_pgn_terminations(pgn_path: Path, engine_names: List[str]) -> dict:
    """Walk a PGN and classify every game's [Termination] header.

    Returns::

        {
          "time_forfeits": {engine_name: count, ...},
          "other_terminations": {engine_name: count, ...},
          "investigation_required": bool,
          "unrecognized_terminations": list[str],
        }

    All ``engine_names`` appear as keys with default 0. Classification
    (case-insensitive, substring match):

      * any of ``TIME_FORFEIT_PATTERNS`` → ``time_forfeits[loser] += 1``
      * any of ``OTHER_NONNORMAL_PATTERNS`` → ``other_terminations[loser] += 1``
      * empty / "normal" → skip
      * everything else → over-flag path: ``investigation_required = True``,
        ``time_forfeits[loser] += 1`` (defensive over-count per §10 Q1) AND
        append the raw string to ``unrecognized_terminations``.
    """
    time_forfeits: Dict[str, int] = {name: 0 for name in engine_names}
    other_terminations: Dict[str, int] = {name: 0 for name in engine_names}
    unrecognized: List[str] = []
    investigation_required = False

    current: Dict[str, str] = {}

    def _flush(game_headers: Dict[str, str]) -> None:
        nonlocal investigation_required
        if not game_headers:
            return
        termination = game_headers.get("Termination", "")
        result = game_headers.get("Result", "")
        white = game_headers.get("White", "")
        black = game_headers.get("Black", "")
        tlower = termination.lower()

        if not termination or tlower in NORMAL_TERMINATIONS:
            return

        loser = _loser_from_result(result, white, black)

        if any(p in tlower for p in TIME_FORFEIT_PATTERNS):
            if loser is not None and loser in time_forfeits:
                time_forfeits[loser] += 1
            return

        if any(p in tlower for p in OTHER_NONNORMAL_PATTERNS):
            if loser is not None and loser in other_terminations:
                other_terminations[loser] += 1
            return

        # Over-flag fallback: unrecognized non-normal string. Better to
        # over-count a forfeit than miss a silent fastchess string change.
        investigation_required = True
        unrecognized.append(termination)
        if loser is not None and loser in time_forfeits:
            time_forfeits[loser] += 1

    try:
        with pgn_path.open("r", encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                line = raw.rstrip("\n").rstrip("\r")
                if not line:
                    continue
                m = _PGN_HEADER_RE.match(line)
                if m:
                    key, value = m.group(1), m.group(2)
                    # New game begins at the [White ...] header (canonical)
                    if key == "White" and current:
                        _flush(current)
                        current = {}
                    current[key] = value
        # Flush trailing game
        _flush(current)
    except FileNotFoundError as exc:
        raise GauntletError(f"PGN not found: {pgn_path}") from exc

    return {
        "time_forfeits": time_forfeits,
        "other_terminations": other_terminations,
        "investigation_required": investigation_required,
        "unrecognized_terminations": unrecognized,
    }


# ---------------------------------------------------------------------------
# Per-move NPS aggregator — D-13 sentinel input
# ---------------------------------------------------------------------------


def collect_per_move_nps(pgn_path: Path, engine_names: List[str]) -> Dict[str, dict]:
    """Aggregate per-move NPS from PGN comment annotations.

    For each ``{ ... nps=N ... }`` PGN tail-comment, attribute the sample
    to the engine that played the move (white on odd plies, black on even
    plies — chess convention: ply 1 == White's first move).

    Returns ``{engine_name: {"median": int|None, "mean": float|None, "samples": int}}``;
    ``median`` / ``mean`` are ``None`` when zero samples were collected.
    """
    samples: Dict[str, List[int]] = {name: [] for name in engine_names}

    white = ""
    black = ""
    ply = 0
    in_game = False

    try:
        fh = pgn_path.open("r", encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise GauntletError(f"PGN not found: {pgn_path}") from exc

    with fh:
        for raw in fh:
            line = raw.rstrip("\n").rstrip("\r")
            if not line:
                continue
            m = _PGN_HEADER_RE.match(line)
            if m:
                key, value = m.group(1), m.group(2)
                if key == "White":
                    # New game begins
                    white = value
                    ply = 0
                    in_game = True
                elif key == "Black":
                    black = value
                continue

            if not in_game:
                continue

            # Movetext line: walk tokens, tracking braces. Each non-comment,
            # non-move-number token that is a SAN move increments the ply.
            i = 0
            n = len(line)
            while i < n:
                ch = line[i]
                if ch.isspace():
                    i += 1
                    continue
                if ch == "{":
                    end = line.find("}", i)
                    if end == -1:
                        # Multi-line comments are uncommon in fastchess PGN;
                        # bail out of this line and let the next iteration
                        # try to recover at the next header.
                        break
                    comment = line[i + 1 : end]
                    nps_match = _NPS_RE.search(comment)
                    if nps_match and ply >= 1:
                        # ply was incremented by the move that PRECEDED this
                        # comment, so ply parity decides the mover.
                        mover = white if (ply % 2 == 1) else black
                        if mover in samples:
                            try:
                                samples[mover].append(int(nps_match.group(1)))
                            except ValueError:
                                pass
                    i = end + 1
                    continue
                # Non-whitespace, non-comment token. Read until next ws / brace.
                j = i
                while j < n and not line[j].isspace() and line[j] != "{":
                    j += 1
                token = line[i:j]
                i = j
                # Skip move numbers ("1." / "1..."), result tokens, NAGs
                if not token:
                    continue
                if token[0].isdigit() and ("." in token or token in ("1-0", "0-1", "1/2-1/2")):
                    if token in ("1-0", "0-1", "1/2-1/2"):
                        in_game = False
                    continue
                if token.startswith("$"):
                    continue
                # Treat anything else as a SAN move
                ply += 1

    result: Dict[str, dict] = {}
    for name in engine_names:
        vals = samples[name]
        if vals:
            result[name] = {
                "median": int(statistics.median(vals)),
                "mean": float(statistics.mean(vals)),
                "samples": len(vals),
            }
        else:
            result[name] = {"median": None, "mean": None, "samples": 0}
    return result


# ---------------------------------------------------------------------------
# Sanity verdict — D-10 boundary inclusive
# ---------------------------------------------------------------------------


def compute_sanity_verdict(elo: float) -> str:
    """Return "PASS" if abs(elo) <= SANITY_TOLERANCE_ELO else "FAIL".

    Boundary inclusive (D-10): ``compute_sanity_verdict(15.0) == "PASS"``.
    """
    if abs(elo) <= SANITY_TOLERANCE_ELO:
        return "PASS"
    return "FAIL"
