"""
Development launcher.

Starts both the FastAPI backend (uvicorn, port 8000) and the Dash
frontend (port 8050) as subprocesses, forwarding their stdout/stderr
to the terminal with colour-coded prefixes.

Usage:
    python run.py
    python run.py --no-reload     # disable uvicorn --reload
    python run.py --backend-only
    python run.py --frontend-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from typing import IO


# ---------------------------------------------------------------------------
# ANSI colour codes (used for prefix labels)
# ---------------------------------------------------------------------------

RESET = "\033[0m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"


def _colour(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


# ---------------------------------------------------------------------------
# Stream forwarder
# ---------------------------------------------------------------------------


def _forward_stream(stream: IO[bytes], prefix: str, colour: str) -> None:
    """Read lines from *stream* and print them with a coloured *prefix*."""
    for raw_line in stream:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
        print(f"{_colour(prefix, colour)} {line}", flush=True)


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------


def _start_backend(reload: bool) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info",
    ]
    if reload:
        cmd.append("--reload")

    print(_colour("[launcher]", YELLOW) + f" Starting backend: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


def _start_frontend() -> subprocess.Popen[bytes]:
    cmd = [sys.executable, "-m", "dashboard.app"]
    print(_colour("[launcher]", YELLOW) + f" Starting frontend: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Quant Research Dashboard launcher")
    parser.add_argument("--no-reload", action="store_true", help="Disable uvicorn auto-reload")
    parser.add_argument("--backend-only", action="store_true", help="Start backend only")
    parser.add_argument("--frontend-only", action="store_true", help="Start frontend only")
    args = parser.parse_args()

    processes: list[subprocess.Popen[bytes]] = []
    threads: list[threading.Thread] = []

    # ---- Start backend --------------------------------------------------
    if not args.frontend_only:
        backend_proc = _start_backend(reload=not args.no_reload)
        processes.append(backend_proc)

        t = threading.Thread(
            target=_forward_stream,
            args=(backend_proc.stdout, "[backend]", GREEN),
            daemon=True,
        )
        t.start()
        threads.append(t)

        if not args.backend_only:
            # Give the backend a moment to initialise before starting the frontend
            print(_colour("[launcher]", YELLOW) + " Waiting 2 s for backend to initialise …")
            time.sleep(2)

    # ---- Start frontend -------------------------------------------------
    if not args.backend_only:
        frontend_proc = _start_frontend()
        processes.append(frontend_proc)

        t = threading.Thread(
            target=_forward_stream,
            args=(frontend_proc.stdout, "[frontend]", CYAN),
            daemon=True,
        )
        t.start()
        threads.append(t)

    # ---- Banner ---------------------------------------------------------
    print()
    print(_colour("=" * 60, YELLOW))
    print(_colour("  Quant Research Dashboard", YELLOW))
    if not args.frontend_only:
        print(_colour("  Backend API : http://localhost:8000", GREEN))
        print(_colour("  API docs    : http://localhost:8000/docs", GREEN))
    if not args.backend_only:
        print(_colour("  Dashboard   : http://localhost:8050", CYAN))
    print(_colour("  Press Ctrl-C to stop all services", YELLOW))
    print(_colour("=" * 60, YELLOW))
    print()

    # ---- Wait for any process to exit -----------------------------------
    try:
        while True:
            for proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(
                        _colour("[launcher]", RED)
                        + f" A process exited with code {ret}. Shutting down …"
                    )
                    _terminate_all(processes)
                    sys.exit(ret)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n" + _colour("[launcher]", YELLOW) + " Ctrl-C received. Shutting down …")
        _terminate_all(processes)


def _terminate_all(processes: list[subprocess.Popen[bytes]]) -> None:
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
