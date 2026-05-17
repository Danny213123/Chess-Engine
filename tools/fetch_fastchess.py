#!/usr/bin/env python3
"""Fetch + cache + checksum-verify the pinned fastchess binary.

Satisfies Phase 2 requirements GAUNT-01 (fastchess prebuilt binary
fetched by script) plus the Phase 2 CONTEXT decisions:

  D-01  modeled on the Syzygy download pattern (no in-tree Python
        analog exists per RESEARCH §6 — this module IS the pattern)
  D-02  pinned upstream release + non-bypassable SHA256 gate
  D-03  cache lives under ``tools/.cache/fastchess{,.exe}`` (gitignored)
  D-04  OS-aware asset selection (Windows / Linux / macOS); single
        entry point with OS detection internal

Trust model
-----------
Upstream (Disservin/fastchess) does NOT publish SHA256s in release
notes. Per RESEARCH §3 the planner picks a tag at plan time, downloads
each per-OS asset once via a trusted second-path session (browser TLS),
re-computes ``sha256sum`` locally, and pastes the verified hashes into
the ``FASTCHESS_ASSETS`` table below. Plan 02-03 Task 2 is the human
checkpoint where those hashes enter the codebase.

Until that checkpoint runs, the constants below hold a sentinel
string (intentionally invalid under ``^[a-f0-9]{64}$`` regex).
``ensure_fastchess()`` refuses to run while any sentinel is present
— the D-02 gate is non-bypassable.

Usage
-----
    >>> from tools.fetch_fastchess import ensure_fastchess
    >>> path = ensure_fastchess()      # returns Path to verified binary

CLI form (used by tools/gauntlet.py and by hand):

    $ python3 tools/fetch_fastchess.py
    /…/tools/.cache/fastchess

Stdlib only — no third-party deps; safe to import before ``uv sync``.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import stat
import sys
import urllib.request
from pathlib import Path

# -----------------------------------------------------------------------------
# PINNED RELEASE CONSTANTS (D-02 trust gate)
# -----------------------------------------------------------------------------
#
# These five values land via Plan 02-03 Task 2's human checkpoint.
# DO NOT replace the sentinels without going through the documented
# verification flow (browser TLS download + local sha256sum compare).
# Bumping the version after Task 2 is a deliberate 4-line PR: edit
# FASTCHESS_RELEASE + the three sha256 fields + run a fresh checkpoint.
FASTCHESS_RELEASE: str = "v1.8.0-alpha"  # e.g. "v1.4.0"

# Per-OS asset table. The ``asset`` field is the exact filename inside
# the GitHub release (the planner records it via the releases API at
# checkpoint time — see RESEARCH §3 / §10 Q2). The ``sha256`` field is
# the locally-re-computed digest the human pastes after second-path
# verification.
FASTCHESS_ASSETS: dict[str, dict[str, str]] = {
    "Windows": {"asset": "v1.8.0-alpha", "sha256": "dcd5ad5c72237410f54dfc6e1af59f1088e72c2f67c29244fc974100791f3d13"},
    "Linux":   {"asset": "v1.8.0-alpha", "sha256": "23bc3774213a2e7db2755510ac974eb5bdc8397867ab1805cc57ccb8c635ba07"},
    "Darwin":  {"asset": "v1.8.0-alpha", "sha256": "5f5a313b8f8d6222a9914ba76f000197e3bfb3c919a12b9e92e6ac5d516b91fc"},
}

# Constant the runtime guard compares against. The literal is split at
# the source level so it does NOT appear as a single token here — only
# the 7 fields above (1 release tag + 3 asset names + 3 sha256s) hold
# the contiguous sentinel string. After the Plan 02-03 Task 2 human
# checkpoint replaces all 7 above, `grep -c PENDING<UNDERSCORE>HUMAN_CHECKPOINT`
# over this file returns 0 — that count is the post-checkpoint
# acceptance test.
_SENTINEL_LITERAL = "PENDING" + "_HUMAN_CHECKPOINT"

# Cache lives under tools/.cache/ (gitignored per D-03 and the .gitignore
# update in Plan 02-03 Task 3). Resolved relative to THIS file so the
# fetcher works regardless of the caller's cwd.
CACHE_DIR: Path = Path(__file__).resolve().parent / ".cache"

_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_CHUNK_SIZE = 1 << 16  # 64 KiB streaming read


# -----------------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------------
def _check_sentinels() -> None:
    """Refuse to run while any checkpoint sentinel remains.

    The D-02 gate is non-bypassable: no asset name and no sha256 may be
    the sentinel literal at the point ``ensure_fastchess()`` is invoked.
    """
    if FASTCHESS_RELEASE == _SENTINEL_LITERAL:
        raise SystemExit(
            "fetch_fastchess: human checkpoint not yet applied — "
            "FASTCHESS_RELEASE is the sentinel. See Plan 02-03 Task 2."
        )
    for host, spec in FASTCHESS_ASSETS.items():
        if spec.get("asset") == _SENTINEL_LITERAL or spec.get("sha256") == _SENTINEL_LITERAL:
            raise SystemExit(
                f"fetch_fastchess: human checkpoint not yet applied — "
                f"FASTCHESS_ASSETS[{host!r}] still holds sentinel "
                f"values. See Plan 02-03 Task 2."
            )
        sha = spec["sha256"]
        if not _SHA256_PATTERN.match(sha):
            raise SystemExit(
                f"fetch_fastchess: FASTCHESS_ASSETS[{host!r}]['sha256'] "
                f"is not a 64-char hex digest: {sha!r}"
            )


def _asset_for_host() -> tuple[str, str]:
    """Return (asset_filename, expected_sha256) for the current OS.

    Raises SystemExit on unsupported OS (e.g. FreeBSD, AIX) — the
    SystemExit message must include the unsupported platform string so
    the operator sees what was rejected.
    """
    host = platform.system()
    spec = FASTCHESS_ASSETS.get(host)
    if spec is None:
        raise SystemExit(
            f"fetch_fastchess: unsupported OS {host!r} — supported: "
            f"{sorted(FASTCHESS_ASSETS.keys())}"
        )
    return spec["asset"], spec["sha256"]


def _sha256(path: Path) -> str:
    """Stream a SHA256 over ``path`` in 64 KiB chunks (constant memory)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _dest_path() -> Path:
    """Return the canonical cache path for THIS host's fastchess binary."""
    name = "fastchess.exe" if platform.system() == "Windows" else "fastchess"
    return CACHE_DIR / name


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------
def ensure_fastchess() -> Path:
    """Idempotent: return the cached fastchess Path, downloading on miss.

    Fast path: if the cached binary's SHA256 matches the pinned digest,
    return its Path with no network I/O.

    Slow path: download the per-host asset from the pinned release,
    streamed to a ``.part`` sibling, atomic-rename on success, verify
    checksum, ``chmod +x`` on POSIX. Checksum mismatch unlinks the
    corrupt file and raises SystemExit (D-02: non-bypassable gate).

    Returns
    -------
    pathlib.Path
        Absolute path to the verified executable under ``CACHE_DIR``.

    Raises
    ------
    SystemExit
        - If any checkpoint sentinel is present.
        - If the current OS is not in ``FASTCHESS_ASSETS``.
        - If the downloaded asset's SHA256 does not match the pinned
          value (corrupt cached file is removed before raising).
    """
    _check_sentinels()
    asset, want_sha = _asset_for_host()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _dest_path()

    # Idempotent fast path — already cached + checksum matches.
    if dest.exists() and _sha256(dest) == want_sha:
        return dest

    # Slow path — download, verify, atomic-rename.
    url = (
        f"https://github.com/Disservin/fastchess/releases/download/"
        f"{FASTCHESS_RELEASE}/{asset}"
    )
    print(f"[fetch_fastchess] downloading {url}", file=sys.stderr)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url) as response, part.open("wb") as out:
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
    except Exception:
        # Mid-read failures must not leave a .part file behind — that
        # would cause the next run to try to checksum a partial file
        # (which would fail) and waste a download.
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass
        raise

    got = _sha256(part)
    if got != want_sha:
        # Corrupt file must NOT be promoted to the canonical name.
        try:
            part.unlink()
        except OSError:
            pass
        # Also remove any stale dest (e.g. older corrupt cache) so the
        # next run re-downloads cleanly.
        if dest.exists():
            try:
                dest.unlink()
            except OSError:
                pass
        raise SystemExit(
            f"fetch_fastchess: checksum mismatch for {asset} — "
            f"want {want_sha}, got {got}. Asset has been removed."
        )

    os.replace(part, dest)

    if platform.system() != "Windows":
        # +x for owner/group/other so the binary is launchable by
        # fastchess subprocess invocations under any euid.
        dest.chmod(
            dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        )

    return dest


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] in ("-h", "--help"):
        sys.stderr.write(
            "usage: python3 tools/fetch_fastchess.py\n"
            "  Idempotent fetch + checksum + cache for the pinned\n"
            "  fastchess release. Prints the cached binary path on\n"
            "  stdout. Exits non-zero on checksum mismatch or while\n"
            "  the Plan 02-03 Task 2 human checkpoint is unresolved.\n"
        )
        return 0
    try:
        path = ensure_fastchess()
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 — top-level CLI catch
        sys.stderr.write(f"fetch_fastchess: {error}\n")
        return 1
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
