from __future__ import annotations

import signal
import threading
from traceback import format_exc

from django.core.management import call_command
from django.core.management.base import BaseCommand

from jobs.execution import local_execution_enabled, run_local_worker_iteration


def run_worker_iteration() -> None:
    """Execute one worker iteration.

    The worker entrypoint stays stable while the runtime backend changes.
    Local mode is the default production path and dispatches queued jobs
    directly to Docker while reconciling running attempts. SLURM mode is
    kept only as a temporary fallback and still delegates to ``poll_jobs``.
    """
    if local_execution_enabled():
        run_local_worker_iteration()
        return
    call_command("poll_jobs")


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def _request_stop(signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)


def run_worker_loop(
    *,
    interval: int,
    stop_event: threading.Event,
    once: bool = False,
    stdout,
    stderr,
) -> None:
    while not stop_event.is_set():
        try:
            run_worker_iteration()
        except Exception:
            stderr.write("Worker iteration failed:")
            stderr.write(format_exc())

        if once:
            return

        if stop_event.wait(interval):
            return


class Command(BaseCommand):
    help = "Run the long-lived job worker loop"

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=int,
            default=10,
            help="Seconds to wait between worker iterations",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single worker iteration and exit",
        )

    def handle(self, *args, **options):
        interval = max(1, int(options["interval"]))
        once = bool(options["once"])
        stop_event = threading.Event()

        _install_signal_handlers(stop_event)

        run_worker_loop(
            interval=interval,
            stop_event=stop_event,
            once=once,
            stdout=self.stdout,
            stderr=self.stderr,
        )
