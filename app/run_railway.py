"""Run the API and ingestion worker in one Railway volume-owning service.

Railway volumes cannot be shared between services. Keeping these processes in one
container allows the API and Celery worker to access the same uploaded files.
"""

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    concurrency = os.getenv("CELERY_CONCURRENCY", "2")
    # Free Render services do not support pre-deploy commands. Apply schema
    # migrations before either process can accept requests or consume jobs.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )
    processes = [
        subprocess.Popen([
            sys.executable, "-m", "celery", "-A", "app.workers.celery_app:celery_app",
            "worker", "--loglevel=INFO", "--hostname=worker@%h", f"--concurrency={concurrency}",
        ]),
        subprocess.Popen([sys.executable, "-m", "app.run_api"]),
    ]

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
