"""Run only this BlueHarbor application. No sibling project is required."""

import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
REQUIREMENTS = BACKEND / "requirements.txt"

sys.path.insert(0, str(BACKEND))

from app_mode import ROLE


children = []


# ---------------------------------------------------------
# Console helpers
# ---------------------------------------------------------

def info(message):
    print(f"[INFO]  {message}", flush=True)


def ok(message):
    print(f"[OK]    {message}", flush=True)


def error(message):
    print(f"[ERROR] {message}", flush=True)


# ---------------------------------------------------------
# Python dependency setup
# ---------------------------------------------------------

def ensure_pip():
    """
    Make sure pip is available for the exact Python interpreter
    that is currently running this launcher.
    """

    result = subprocess.run(
        [sys.executable, "-m", "pip", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode == 0:
        ok("pip is available.")
        return

    info("pip was not found. Installing pip...")

    subprocess.run(
        [sys.executable, "-m", "ensurepip", "--upgrade"],
        cwd=ROOT,
        check=True,
    )

    ok("pip installed successfully.")


def install_backend_dependencies():
    """
    Install/update requirements using the same Python executable
    that launched this file.

    This avoids depending on the Windows `python` PATH alias.
    """

    if not REQUIREMENTS.exists():
        raise RuntimeError(
            f"Backend requirements file was not found:\n{REQUIREMENTS}"
        )

    ensure_pip()

    info("Checking backend Python dependencies...")

    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(REQUIREMENTS),
        "--disable-pip-version-check",
    ]

    result = subprocess.run(
        command,
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Backend dependency installation failed.\n"
            "Check the pip error shown above."
        )

    ok("Backend Python dependencies are ready.")


def verify_backend_dependencies():
    """
    Final validation for critical runtime packages.
    """

    required_modules = {
        "psycopg": "PostgreSQL / Supabase database driver",
        "reportlab": "PDF generation",
    }

    missing = []

    for module, description in required_modules.items():
        if importlib.util.find_spec(module) is None:
            missing.append(f"{module} ({description})")

    if missing:
        raise RuntimeError(
            "Some required backend dependencies are still unavailable:\n"
            + "\n".join(f" - {item}" for item in missing)
        )

    ok("Critical backend modules verified.")


# ---------------------------------------------------------
# Port management
# ---------------------------------------------------------

def ports():
    sockets = []

    try:
        preferred_ports = (
            (3000, 8001)
            if ROLE == "buyer"
            else (3001, 8002)
        )

        for preferred in preferred_ports:
            sock = socket.socket()

            try:
                sock.bind(("127.0.0.1", preferred))
            except OSError:
                sock.bind(("127.0.0.1", 0))

            sockets.append(sock)

        return tuple(sock.getsockname()[1] for sock in sockets)

    finally:
        for sock in sockets:
            sock.close()


# ---------------------------------------------------------
# Process management
# ---------------------------------------------------------

def start(args, env):
    child = subprocess.Popen(
        args,
        cwd=ROOT,
        env=env,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if os.name == "nt"
            else 0
        ),
    )

    children.append(child)
    return child


def ready(url, timeout=90):
    until = time.monotonic() + timeout

    while time.monotonic() < until:

        if any(process.poll() is not None for process in children):
            raise RuntimeError(
                "A BlueHarbor service stopped unexpectedly. "
                "Check the terminal messages above."
            )

        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return

        except Exception:
            pass

        time.sleep(0.5)

    raise RuntimeError(
        "Startup timed out. "
        "Check Supabase configuration and the messages above."
    )


# ---------------------------------------------------------
# Frontend dependency setup
# ---------------------------------------------------------

def find_npm():
    npm = shutil.which(
        "npm.cmd" if os.name == "nt" else "npm"
    )

    if not npm:
        raise RuntimeError(
            "Node.js / npm was not found.\n"
            "Install Node.js 22.13+ and reopen VS Code."
        )

    return npm


def install_frontend_dependencies(npm, frontend_env):
    vinext_candidates = [
        ROOT / "node_modules" / ".bin" / "vinext",
        ROOT / "node_modules" / ".bin" / "vinext.cmd",
    ]

    if any(path.exists() for path in vinext_candidates):
        ok("Frontend dependencies are ready.")
        return

    package_json = ROOT / "package.json"

    if not package_json.exists():
        raise RuntimeError(
            f"package.json was not found:\n{package_json}"
        )

    info("Frontend dependencies are missing.")
    info("Installing frontend packages. This may take a few minutes...")

    package_lock = ROOT / "package-lock.json"

    if package_lock.exists():
        command = [
            npm,
            "ci",
            "--no-audit",
            "--no-fund",
        ]
    else:
        command = [
            npm,
            "install",
            "--no-audit",
            "--no-fund",
        ]

    subprocess.run(
        command,
        cwd=ROOT,
        env=frontend_env,
        check=True,
    )

    ok("Frontend packages installed successfully.")


# ---------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------

def acquire_launcher_lock():
    lock = open(ROOT / ".launcher.lock", "a+b")

    lock.seek(0)
    lock.write(b"0")
    lock.flush()
    lock.seek(0)

    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(
                lock.fileno(),
                msvcrt.LK_NBLCK,
                1,
            )
        except OSError:
            lock.close()
            raise RuntimeError(
                "This BlueHarbor application is already running.\n"
                "Use its existing terminal or stop it with Ctrl+C."
            )

    else:
        import fcntl

        try:
            fcntl.flock(
                lock,
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except OSError:
            lock.close()
            raise RuntimeError(
                "This BlueHarbor application is already running."
            )

    return lock


# ---------------------------------------------------------
# Main launcher
# ---------------------------------------------------------

def main():

    print()
    print("=" * 62)
    print(f" BlueHarbor {ROLE.capitalize()} Portal")
    print(" Local environment check & launcher")
    print("=" * 62)
    print()

    ok(f"Python {sys.version.split()[0]}")
    info(f"Python executable: {sys.executable}")
    info(f"Project directory: {ROOT}")

    # -----------------------------------------------------
    # 1. Python dependencies
    # -----------------------------------------------------

    install_backend_dependencies()
    verify_backend_dependencies()

    # Import configuration AFTER dependencies are installed.
    import cloud_config

    info("Checking BlueHarbor configuration...")
    cloud_config.validate()
    ok("Backend configuration validated.")

    # -----------------------------------------------------
    # 2. Node / npm
    # -----------------------------------------------------

    npm = find_npm()

    try:
        npm_version = subprocess.check_output(
            [npm, "--version"],
            text=True,
        ).strip()

        ok(f"npm {npm_version}")

    except Exception:
        ok("npm detected.")

    # -----------------------------------------------------
    # 3. Prevent duplicate launcher
    # -----------------------------------------------------

    launcher_lock = acquire_launcher_lock()

    # Keep reference alive until application stops.
    _ = launcher_lock

    # -----------------------------------------------------
    # 4. Select available ports
    # -----------------------------------------------------

    web_port, api_port = ports()

    info(f"Frontend port: {web_port}")
    info(f"Backend API port: {api_port}")

    # -----------------------------------------------------
    # 5. Environment
    # -----------------------------------------------------

    env = os.environ.copy()

    env.update(
        BLUEHARBOR_WEB_PORT=str(web_port),
        BLUEHARBOR_WEB_PORTS=str(web_port),
        BLUEHARBOR_API_PORT=str(api_port),
        NEXT_PUBLIC_BUYER_URL=os.environ.get(
            "BLUEHARBOR_BUYER_URL",
            f"http://localhost:{web_port}",
        ),
        PYTHONUNBUFFERED="1",
    )

    # IMPORTANT:
    # Never expose backend secrets to the frontend process.
    frontend_env = {
        key: value
        for key, value in env.items()
        if not key.startswith(
            (
                "SUPABASE_",
                "SMTP_",
                "OLLAMA_",
                "BLUEHARBOR_SMTP_",
                "BLUEHARBOR_AI_",
                "GEMINI_",
            )
        )
    }

    # -----------------------------------------------------
    # 6. Frontend dependencies
    # -----------------------------------------------------

    install_frontend_dependencies(
        npm,
        frontend_env,
    )

    # -----------------------------------------------------
    # 7. Start backend
    # -----------------------------------------------------

    info("Starting BlueHarbor backend...")

    start(
        [
            sys.executable,
            str(BACKEND / "server.py"),
        ],
        env,
    )

    ready(
        f"http://127.0.0.1:{api_port}/api/health",
        timeout=35,
    )

    ok("Backend API is running.")

    # -----------------------------------------------------
    # 8. Start frontend
    # -----------------------------------------------------

    info("Starting BlueHarbor frontend...")

    start(
        [
            npm,
            "run",
            "dev",
            "--",
            "--port",
            str(web_port),
        ],
        frontend_env,
    )

    suffix = "/admin" if ROLE == "admin" else "/"

    ready(
        f"http://127.0.0.1:{web_port}{suffix}",
        timeout=90,
    )

    ok("Frontend is running.")

    # -----------------------------------------------------
    # 9. Open browser
    # -----------------------------------------------------

    url = f"http://localhost:{web_port}{suffix}"

    print()
    print("=" * 62)
    print(f" BlueHarbor {ROLE.capitalize()} is ready")
    print("=" * 62)
    print()
    print(f" URL           : {url}")
    print(f" Configuration : {BACKEND / '.env'}")
    print()
    print(" Only this BlueHarbor application is running.")
    print(" Press Ctrl+C to stop all of its services.")
    print()

    if "--no-browser" not in sys.argv:
        webbrowser.open(url)

    # Keep launcher alive.
    while all(process.poll() is None for process in children):
        time.sleep(1)

    raise RuntimeError(
        "A BlueHarbor service stopped unexpectedly. "
        "See its terminal output above."
    )


# ---------------------------------------------------------
# Shutdown
# ---------------------------------------------------------

if __name__ == "__main__":

    failed = False

    try:
        main()

    except KeyboardInterrupt:
        print()
        info("Stopping BlueHarbor...")

    except subprocess.CalledProcessError as exc:
        error(
            f"A dependency installation or startup command failed "
            f"with exit code {exc.returncode}."
        )
        failed = True

    except RuntimeError as exc:
        error(str(exc))
        failed = True

    except Exception as exc:
        error(f"Unexpected launcher error: {exc}")
        failed = True

    finally:

        for child in reversed(children):

            if child.poll() is None:

                if os.name == "nt":
                    subprocess.run(
                        [
                            "taskkill",
                            "/PID",
                            str(child.pid),
                            "/T",
                            "/F",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                else:
                    child.terminate()

        if children:
            ok("BlueHarbor services stopped.")

    sys.exit(1 if failed else 0)