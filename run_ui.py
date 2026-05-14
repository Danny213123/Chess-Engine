import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import webbrowser


PROJECT_ROOT = Path(__file__).resolve().parent
CLIENT_DIR = PROJECT_ROOT / "client"
UV_BOOTSTRAP_ENV = "CHESS_ENGINE_UV_BOOTSTRAPPED"


def _missing_server_dependencies():
    required_modules = ("uvicorn", "fastapi", "pydantic", "chess_engine")
    return [module for module in required_modules if importlib.util.find_spec(module) is None]


def ensure_server_dependencies():
    missing = _missing_server_dependencies()
    if not missing:
        return

    print("Missing backend dependencies: " + ", ".join(missing))
    uv_path = shutil.which("uv")
    if uv_path and os.environ.get(UV_BOOTSTRAP_ENV) != "1":
        print("Re-launching with uv so Python dependencies are installed automatically...")
        env = os.environ.copy()
        env[UV_BOOTSTRAP_ENV] = "1"
        os.execvpe(
            uv_path,
            [uv_path, "run", "python", str(Path(__file__).resolve())],
            env,
        )
    elif importlib.util.find_spec("uv") is not None and os.environ.get(UV_BOOTSTRAP_ENV) != "1":
        print("Re-launching with python -m uv so Python dependencies are installed automatically...")
        env = os.environ.copy()
        env[UV_BOOTSTRAP_ENV] = "1"
        os.execvpe(
            sys.executable,
            [sys.executable, "-m", "uv", "run", "python", str(Path(__file__).resolve())],
            env,
        )

    print("Installing backend dependencies with: python -m pip install -e .")

    subprocess.check_call([
        sys.executable,
        "-m",
        "pip",
        "install",
        "-e",
        ".",
    ], cwd=PROJECT_ROOT)

    still_missing = _missing_server_dependencies()
    if still_missing:
        raise RuntimeError(
            "Dependency installation completed, but these modules are still missing: "
            + ", ".join(still_missing)
        )


def ensure_frontend_build():
    dist_index = CLIENT_DIR / "dist" / "index.html"
    if dist_index.exists():
        return

    npm_path = shutil.which("npm")
    if not npm_path:
        raise RuntimeError("npm is required to install and build the React frontend.")

    if not (CLIENT_DIR / "node_modules").exists():
        install_command = [npm_path, "ci", "--prefix", "client"]
        if not (CLIENT_DIR / "package-lock.json").exists():
            install_command = [npm_path, "install", "--prefix", "client"]

        print("Installing frontend dependencies with: " + " ".join(install_command))
        subprocess.check_call(install_command, cwd=PROJECT_ROOT)

    print("Building frontend with: npm run build --prefix client")
    subprocess.check_call([npm_path, "run", "build", "--prefix", "client"], cwd=PROJECT_ROOT)


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    ensure_server_dependencies()
    ensure_frontend_build()

    import uvicorn

    # Start browser in background
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run server
    print("Starting Chess Engine UI...")
    uvicorn.run("chess_engine.server.app:app", host="0.0.0.0", port=8000, reload=False)
