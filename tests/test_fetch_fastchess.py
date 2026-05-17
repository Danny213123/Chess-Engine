"""Unit tests for tools/fetch_fastchess.py (Plan 02-03 Task 4).

Covers the post-checkpoint behavior contract:
  - test_idempotent_when_cached: cache hit fast path makes NO network call
  - test_checksum_mismatch_raises: corrupt download is unlinked + SystemExit
  - test_asset_for_host_windows / _linux / _darwin: OS dispatch correctness
  - test_asset_for_host_unsupported: unsupported OS raises SystemExit with name
  - test_executable_bit_set_on_posix: +x granted on POSIX after fresh fetch
  - test_atomic_write_does_not_leak_partial: mid-read failure cleans .part
  - test_constants_no_sentinels: pins the Plan 02-03 Task 2 outcome

All tests monkeypatch `urllib.request.urlopen` — NO real network calls.
Each test stages a synthetic CACHE_DIR under pytest's `tmp_path` so the
real `tools/.cache/` is never touched.

Runtime budget: < 5 s.
"""

from __future__ import annotations

import hashlib
import io
import platform
import re
import stat
from pathlib import Path

import pytest


# Module under test: import via the package path so PEP 420 / explicit
# tools/__init__.py both work.
from tools import fetch_fastchess as ff


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
class _FakeResponse:
    """Minimal urlopen() context manager returning a fixed byte payload.

    fetch_fastchess streams via `.read(_CHUNK_SIZE)` in a loop until an
    empty bytes object is returned, so we model that protocol.
    """

    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class _RaisingResponse:
    """urlopen() context manager whose .read() raises mid-stream.

    Used to exercise the atomic-write cleanup path — fetch_fastchess
    MUST unlink the *.part file before propagating the exception so the
    next run does not see a stale partial.
    """

    def __init__(self, exc: Exception):
        self._exc = exc
        self._first = True

    def read(self, size: int = -1) -> bytes:
        if self._first:
            self._first = False
            # Emit a small initial chunk so the .part file actually
            # appears on disk before the failure occurs.
            return b"partial-prefix-bytes"
        raise self._exc

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _patch_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect CACHE_DIR + _dest_path to point under tmp_path."""
    cache = tmp_path / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ff, "CACHE_DIR", cache)
    # _dest_path resolves CACHE_DIR + per-OS name at call time; since
    # CACHE_DIR is module-level and we just patched it, no further
    # patching needed.
    return cache


def _patch_assets(monkeypatch: pytest.MonkeyPatch, sha: str, asset: str = "fc-test") -> None:
    """Replace FASTCHESS_ASSETS so all 3 OS rows point at a synthetic
    asset + sha. The fetcher dispatches on platform.system() at call
    time; tests that need to force the host OS monkeypatch that
    separately.
    """
    monkeypatch.setattr(
        ff,
        "FASTCHESS_ASSETS",
        {
            "Windows": {"asset": asset, "sha256": sha},
            "Linux":   {"asset": asset, "sha256": sha},
            "Darwin":  {"asset": asset, "sha256": sha},
        },
    )


# -----------------------------------------------------------------------------
# Tests — behavior contract
# -----------------------------------------------------------------------------
def test_constants_no_sentinels():
    """Pin the Plan 02-03 Task 2 human-checkpoint outcome.

    No constant may equal the PENDING_HUMAN_CHECKPOINT literal; every
    sha256 must match the 64-char hex regex.
    """
    sentinel = "PENDING" + "_HUMAN_CHECKPOINT"
    assert ff.FASTCHESS_RELEASE != sentinel, (
        "FASTCHESS_RELEASE still holds the sentinel — Plan 02-03 Task 2 "
        "human checkpoint has not been applied."
    )
    hex64 = re.compile(r"^[a-f0-9]{64}$")
    for host, spec in ff.FASTCHESS_ASSETS.items():
        assert spec["asset"] != sentinel, f"asset for {host!r} is sentinel"
        assert spec["sha256"] != sentinel, f"sha256 for {host!r} is sentinel"
        assert hex64.match(spec["sha256"]), (
            f"FASTCHESS_ASSETS[{host!r}]['sha256'] is not 64-char hex: "
            f"{spec['sha256']!r}"
        )


def test_idempotent_when_cached(tmp_path, monkeypatch):
    """Cache hit + checksum match returns Path with NO network I/O."""
    payload = b"already-cached-fastchess-binary-payload-x"
    sha = _sha256_bytes(payload)
    cache = _patch_cache(monkeypatch, tmp_path)
    _patch_assets(monkeypatch, sha)

    # Stage the cached binary at the expected dest path.
    dest = ff._dest_path()
    dest.write_bytes(payload)

    def _no_network(*args, **kwargs):
        raise RuntimeError("no network call expected on cache hit")

    monkeypatch.setattr(ff.urllib.request, "urlopen", _no_network)

    result = ff.ensure_fastchess()
    assert result == dest
    assert dest.read_bytes() == payload


def test_checksum_mismatch_raises(tmp_path, monkeypatch):
    """Wrong-bytes download must SystemExit AND unlink the corrupt file."""
    expected_sha = _sha256_bytes(b"the-correct-payload")
    served_payload = b"NOT-the-correct-payload"  # different sha

    _patch_cache(monkeypatch, tmp_path)
    _patch_assets(monkeypatch, expected_sha)

    monkeypatch.setattr(
        ff.urllib.request,
        "urlopen",
        lambda *a, **kw: _FakeResponse(served_payload),
    )

    with pytest.raises(SystemExit) as excinfo:
        ff.ensure_fastchess()
    assert "checksum mismatch" in str(excinfo.value)

    dest = ff._dest_path()
    assert not dest.exists(), "corrupt download must be unlinked"
    part = dest.with_suffix(dest.suffix + ".part")
    assert not part.exists(), ".part sibling must be cleaned"


def test_asset_for_host_windows(monkeypatch):
    monkeypatch.setattr(ff.platform, "system", lambda: "Windows")
    _patch_assets(monkeypatch, "f" * 64, asset="fc-win.exe")
    asset, sha = ff._asset_for_host()
    assert asset == "fc-win.exe"
    assert sha == "f" * 64


def test_asset_for_host_linux(monkeypatch):
    monkeypatch.setattr(ff.platform, "system", lambda: "Linux")
    _patch_assets(monkeypatch, "a" * 64, asset="fc-linux")
    asset, sha = ff._asset_for_host()
    assert asset == "fc-linux"
    assert sha == "a" * 64


def test_asset_for_host_darwin(monkeypatch):
    monkeypatch.setattr(ff.platform, "system", lambda: "Darwin")
    _patch_assets(monkeypatch, "b" * 64, asset="fc-mac")
    asset, sha = ff._asset_for_host()
    assert asset == "fc-mac"
    assert sha == "b" * 64


def test_asset_for_host_unsupported(monkeypatch):
    """Unsupported OS must SystemExit with the OS name in the message."""
    monkeypatch.setattr(ff.platform, "system", lambda: "FreeBSD")
    with pytest.raises(SystemExit) as excinfo:
        ff._asset_for_host()
    assert "FreeBSD" in str(excinfo.value)


@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="chmod +x is POSIX-only; Windows ignores user-execute bit",
)
def test_executable_bit_set_on_posix(tmp_path, monkeypatch):
    """After a fresh fetch, the user-execute bit must be set on POSIX."""
    payload = b"fresh-posix-payload"
    sha = _sha256_bytes(payload)
    _patch_cache(monkeypatch, tmp_path)
    _patch_assets(monkeypatch, sha)

    monkeypatch.setattr(
        ff.urllib.request,
        "urlopen",
        lambda *a, **kw: _FakeResponse(payload),
    )

    dest = ff.ensure_fastchess()
    mode = dest.stat().st_mode
    assert mode & stat.S_IXUSR, "user-execute bit not set after POSIX fetch"


def test_atomic_write_does_not_leak_partial(tmp_path, monkeypatch):
    """Mid-read failure must clean the .part sibling, leave no stale file."""
    sha = _sha256_bytes(b"would-be-good-payload")
    cache = _patch_cache(monkeypatch, tmp_path)
    _patch_assets(monkeypatch, sha)

    monkeypatch.setattr(
        ff.urllib.request,
        "urlopen",
        lambda *a, **kw: _RaisingResponse(OSError("network died mid-read")),
    )

    with pytest.raises(OSError):
        ff.ensure_fastchess()

    # No .part residue, no canonical file either.
    leftover_parts = list(cache.glob("*.part"))
    assert leftover_parts == [], f"stale .part files: {leftover_parts}"
    dest = ff._dest_path()
    assert not dest.exists(), "canonical dest must not exist after failure"
