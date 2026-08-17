"""Run the API and ingestion worker in one Railway volume-owning service.

Railway volumes cannot be shared between services. Keeping these processes in one
container allows the API and Celery worker to access the same uploaded files.
"""

import os
import signal
import subprocess
import sys
import time


def run_migrations() -> bool:
    """Apply migrations with retries for temporarily unavailable managed DBs."""
    attempts = max(1, int(os.getenv("MIGRATION_MAX_ATTEMPTS", "12")))
    delay = max(1.0, float(os.getenv("MIGRATION_RETRY_SECONDS", "5")))

    for attempt in range(1, attempts + 1):
        print(
            f"Applying database migrations (attempt {attempt}/{attempts})...",
            flush=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            check=False,
        )
        if result.returncode == 0:
            print("Database migrations completed.", flush=True)
            return True
        if attempt < attempts:
            print(
                f"Migration failed; retrying in {delay:g} seconds.",
                flush=True,
            )
            time.sleep(delay)

    print("Database migrations failed after all retry attempts.", flush=True)
    return False


def main() -> int:
    concurrency = os.getenv("CELERY_CONCURRENCY", "2")
    # Bind the platform-provided port immediately. Managed databases can take
    # several seconds to become reachable during a deployment, and blocking API
    # startup on the first migration attempt causes platform health checks to
    # incorrectly report that no process is listening.
    api = subprocess.Popen([sys.executable, "-m", "app.run_api"])
    processes = [api]

    if not run_migrations():
        api.terminate()
        try:
            api.wait(timeout=20)
        except subprocess.TimeoutExpired:
            api.kill()
        return 1

    processes.append(subprocess.Popen([
        sys.executable, "-m", "celery", "-A", "app.workers.celery_app:celery_app",
        "worker", "--loglevel=INFO", "--hostname=worker@%h", f"--concurrency={concurrency}",
    ]))

    stopping = False

    def stop(signum: int, _frame: object) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        for process in processes:
            if process.poll() is None:
                process.send_signal(signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    try:
        while True:
            for process in processes:
                code = process.poll()
                if code is not None:
                    stop(signal.SIGTERM, None)
                    deadline = time.monotonic() + 20
                    for sibling in processes:
                        if sibling is not process and sibling.poll() is None:
                            try:
                                sibling.wait(timeout=max(0, deadline - time.monotonic()))
                            except subprocess.TimeoutExpired:
                                sibling.kill()
                    return code
            time.sleep(0.5)
    finally:
        stop(signal.SIGTERM, None)


if __name__ == "__main__":
    raise SystemExit(main())
