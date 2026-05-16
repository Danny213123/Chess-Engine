"""Build support for the V7 native engine module."""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[4]
V7_DIR = Path(__file__).resolve().parent
BUILD_DIR = V7_DIR / "build"
MODULE_PREFIX = "v7_engine"


class V7BuildError(RuntimeError):
    """Raised when the V7 native module cannot be built."""


@dataclass(frozen=True)
class V7BuildResult:
    module_path: Path
    built: bool


def _module_suffixes() -> tuple[str, ...]:
    if sys.platform == "win32":
        return (".pyd",)
    if sys.platform == "darwin":
        return (".so", ".dylib")
    return (".so",)


def find_packaged_module() -> Path | None:
    """Return an existing packaged v7_engine module, if one is present."""
    suffixes = _module_suffixes()
    for module_path in sorted(V7_DIR.glob(f"{MODULE_PREFIX}*")):
        lower_name = module_path.name.lower()
        if any(lower_name.endswith(suffix) for suffix in suffixes):
            return module_path
    return None


def _find_built_module() -> Path | None:
    suffixes = _module_suffixes()
    candidate_dirs = (
        BUILD_DIR / "Release",
        BUILD_DIR / "RelWithDebInfo",
        BUILD_DIR / "Debug",
        BUILD_DIR,
    )
    for directory in candidate_dirs:
        if not directory.exists():
            continue
        for module_path in sorted(directory.glob(f"{MODULE_PREFIX}*")):
            lower_name = module_path.name.lower()
            if any(lower_name.endswith(suffix) for suffix in suffixes):
                return module_path
    return None


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text.strip()
    return text[-limit:].strip()


def _run(command: list[str], cwd: Path, error_prefix: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        detail = _tail(result.stdout)
        raise V7BuildError(f"{error_prefix}\n{detail}" if detail else error_prefix)
    return result


def _sync_build_dependencies() -> None:
    if importlib.util.find_spec("pybind11") is not None:
        return

    uv_path = shutil.which("uv")
    if not uv_path:
        raise V7BuildError(
            "V7 build requires pybind11. Install uv, then run "
            "`python3 -m uv sync --extra build` or `node cli/bin/chess-engine.js build v7`."
        )

    _run(
        [uv_path, "sync", "--extra", "build"],
        PROJECT_ROOT,
        "Failed to install V7 build dependencies with uv.",
    )
    importlib.invalidate_caches()

    if importlib.util.find_spec("pybind11") is None:
        raise V7BuildError(
            "uv installed the V7 build dependencies, but this Python process still "
            "cannot import pybind11. Restart with `python3 -m uv run python run_ui.py`."
        )


def build_v7_native(force: bool = False) -> V7BuildResult:
    """Build and install the V7 native Python extension into the package."""
    existing_module = find_packaged_module()
    if existing_module and not force:
        return V7BuildResult(module_path=existing_module, built=False)

    cmake_path = shutil.which("cmake")
    if not cmake_path:
        raise V7BuildError(
            "CMake is required to build V7. Install CMake and a C++17 compiler, "
            "then try selecting V7 again."
        )

    # Plan 05 lands the Fathom submodule under extern/fathom; surface a
    # clear diagnostic if the submodule isn't fetched yet so users know to
    # run the git command. Plan 01 ships no Fathom dependency, so we only
    # warn (don't fail) when the directory is missing — the build itself
    # is unaffected this phase.
    fathom_src = V7_DIR / "extern" / "fathom" / "src" / "tbprobe.c"
    if (V7_DIR / "extern" / "fathom").exists() and not fathom_src.exists():
        raise V7BuildError(
            "V7 build requires Fathom (extern/fathom/src/tbprobe.c) but it was not found. "
            "Run 'git submodule update --init --recursive' first to fetch Fathom "
            "(extern/fathom/src/tbprobe.c)."
        )

    _sync_build_dependencies()
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    _run(
        [
            cmake_path,
            "..",
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DPython3_EXECUTABLE={sys.executable}",
        ],
        BUILD_DIR,
        "Failed to configure the V7 native build with CMake.",
    )
    _run(
        [cmake_path, "--build", ".", "--config", "Release"],
        BUILD_DIR,
        "Failed to compile the V7 native engine.",
    )

    built_module = _find_built_module()
    if built_module is None:
        raise V7BuildError("V7 build completed, but no v7_engine module was produced.")

    destination = V7_DIR / built_module.name
    if built_module.resolve() != destination.resolve():
        shutil.copy2(built_module, destination)

    return V7BuildResult(module_path=destination, built=True)


def main() -> int:
    try:
        result = build_v7_native(force=True)
    except V7BuildError as error:
        print(f"V7 build failed: {error}", file=sys.stderr)
        return 1

    state = "built" if result.built else "already available"
    print(f"V7 native module {state}: {result.module_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
