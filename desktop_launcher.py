"""One-click Windows launcher for the local JobLink web application."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import traceback
from urllib.request import urlopen
import webbrowser


APP_NAME = "JobLink Tracker"
HOST = "127.0.0.1"
PORT = 5050
APP_URL = f"http://{HOST}:{PORT}"
_DESKTOP_LOG_STREAM = None


def app_data_dir(environ=None) -> Path:
    env = os.environ if environ is None else environ
    base = env.get("LOCALAPPDATA") or env.get("APPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / "AppData" / "Local" / APP_NAME


def configure_environment(environ=None, frozen=None) -> Path:
    env = os.environ if environ is None else environ
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    data_dir = app_data_dir(env)

    env.setdefault("JOBLINK_ENV", "local")
    env.setdefault("JOBLINK_CAPTURE_ENABLED", "true")
    env.setdefault("JOBLINK_VERIFY_BROWSER_ON_STARTUP", "true")
    env.setdefault("JOBLINK_LOG_DIR", str(data_dir / "logs"))
    env.setdefault("JOBLINK_SCRAPE_WORKERS", "2")
    env.setdefault("JOBLINK_MAX_PENDING_JOBS", "20")
    if is_frozen:
        env.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")

    return data_dir


def configure_output_streams(data_dir: Path):
    """Give windowed PyInstaller builds a real target for Python logging."""
    global _DESKTOP_LOG_STREAM
    if sys.stdout is not None and sys.stderr is not None:
        return None

    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _DESKTOP_LOG_STREAM = (log_dir / "desktop.log").open(
        "a", encoding="utf-8", buffering=1
    )
    if sys.stdout is None:
        sys.stdout = _DESKTOP_LOG_STREAM
    if sys.stderr is None:
        sys.stderr = _DESKTOP_LOG_STREAM
    return _DESKTOP_LOG_STREAM


def is_joblink_running(timeout: float = 0.8) -> bool:
    try:
        with urlopen(f"{APP_URL}/health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("status") == "ok"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def port_is_in_use(timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout):
            return True
    except OSError:
        return False


def wait_until_started(timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_joblink_running(timeout=0.5):
            return True
        time.sleep(0.15)
    return False


def write_startup_error(data_dir: Path) -> Path:
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "desktop_startup_error.log"
    path.write_text(traceback.format_exc(), encoding="utf-8")
    return path


def show_existing_app() -> int:
    from tkinter import messagebox

    webbrowser.open(APP_URL, new=2)
    messagebox.showinfo(APP_NAME, "JobLink is already running, so I opened it in your browser.")
    return 0


def show_port_error() -> int:
    from tkinter import messagebox

    messagebox.showerror(
        APP_NAME,
        "JobLink needs local port 5050, but another program is using it. Close that program and try again.",
    )
    return 1


def run_control_window(server, flask_app, shutdown_app) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.title(APP_NAME)
    root.configure(background="#fff1ea")
    root.resizable(False, False)
    root.geometry("390x178")

    frame = tk.Frame(
        root,
        background="#fffdfb",
        highlightbackground="#ecd3c8",
        highlightthickness=1,
        padx=22,
        pady=18,
    )
    frame.pack(fill="both", expand=True, padx=12, pady=12)

    tk.Label(
        frame,
        text="JobLink is ready",
        background="#fffdfb",
        foreground="#2f282a",
        font=("Calibri", 14, "bold"),
        anchor="w",
    ).pack(fill="x")

    status = tk.StringVar(value=f"Local app: {APP_URL}")
    tk.Label(
        frame,
        textvariable=status,
        background="#fffdfb",
        foreground="#75646a",
        font=("Calibri", 10),
        anchor="w",
        pady=7,
    ).pack(fill="x")

    actions = tk.Frame(frame, background="#fffdfb")
    actions.pack(fill="x", pady=(8, 0))

    open_button = tk.Button(
        actions,
        text="Open JobLink",
        command=lambda: webbrowser.open(APP_URL, new=2),
        background="#c74f32",
        activebackground="#a83f28",
        foreground="#ffffff",
        activeforeground="#ffffff",
        relief="flat",
        borderwidth=0,
        cursor="hand2",
        font=("Calibri", 10, "bold"),
        padx=15,
        pady=7,
    )
    open_button.pack(side="left")

    stopped = threading.Event()
    stopping = False

    def shutdown_worker():
        try:
            server.shutdown()
            server.server_close()
            shutdown_app(flask_app, wait=False)
        finally:
            stopped.set()

    def poll_shutdown():
        if stopped.is_set():
            root.destroy()
            return
        root.after(100, poll_shutdown)

    def stop_app():
        nonlocal stopping
        if stopping:
            return
        stopping = True
        status.set("Closing JobLink...")
        open_button.configure(state="disabled")
        stop_button.configure(state="disabled")
        threading.Thread(target=shutdown_worker, daemon=True).start()
        poll_shutdown()

    stop_button = tk.Button(
        actions,
        text="Stop",
        command=stop_app,
        background="#fffdfb",
        activebackground="#fff1ea",
        foreground="#2f282a",
        relief="solid",
        borderwidth=1,
        cursor="hand2",
        font=("Calibri", 10),
        padx=15,
        pady=6,
    )
    stop_button.pack(side="left", padx=(10, 0))

    root.protocol("WM_DELETE_WINDOW", stop_app)
    root.after(250, lambda: webbrowser.open(APP_URL, new=2))
    root.mainloop()


def main() -> int:
    from tkinter import messagebox

    data_dir = configure_environment()
    configure_output_streams(data_dir)
    try:
        if is_joblink_running():
            return show_existing_app()
        if port_is_in_use():
            return show_port_error()

        from werkzeug.serving import make_server
        from scraper.app import app, shutdown_app

        server = make_server(HOST, PORT, app, threaded=True)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        if not wait_until_started():
            server.shutdown()
            server.server_close()
            shutdown_app(app, wait=False)
            raise RuntimeError("JobLink did not finish starting.")

        run_control_window(server, app, shutdown_app)
        return 0
    except Exception:
        error_path = write_startup_error(data_dir)
        messagebox.showerror(
            APP_NAME,
            f"JobLink could not start. I saved the technical details here:\n{error_path}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
