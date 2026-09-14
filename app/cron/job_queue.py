"""Single-worker FIFO job queue.

Every job used to take one shared `job_lock` directly on whatever thread asked
for it -- the scheduler thread, or a web thread coming in through
/api/job/*. A slow TDLib call therefore blocked web requests indefinitely, and
APScheduler's max_instances let repeat firings pile up behind the same lock.

Here one worker thread owns all job execution, so callers never block: they
submit and get an immediate answer. Two rules keep the queue honest:

  * dedupe -- a job already waiting is not queued a second time,
  * min_interval -- a job that ran recently is skipped rather than run early.
"""

import threading
import queue as queue_module
import time
from datetime import datetime


# Reasons a submit() did not result in a new queue entry.
SUBMITTED = "submitted"
ALREADY_QUEUED = "already_queued"
RUNNING = "running"
TOO_EARLY = "too_early"


class Job:
    def __init__(self, name, func, min_interval, timeout=None):
        # min_interval/timeout are seconds.
        self.name = name
        self.func = func
        self.min_interval = min_interval
        self.timeout = timeout
        self.last_started_at = None
        self.last_finished_at = None
        self.last_error = None
        self.run_count = 0
        self.skipped_early = 0

    def seconds_until_eligible(self, now=None):
        """0 when the job may run, else the seconds still to wait."""
        if self.last_finished_at is None:
            return 0
        now = now if now is not None else time.monotonic()
        elapsed = now - self.last_finished_at
        remaining = self.min_interval - elapsed
        return remaining if remaining > 0 else 0


class JobQueue:
    def __init__(self):
        self._jobs = {}
        self._queue = queue_module.Queue()
        self._pending = set()
        self._running = None
        self._state_lock = threading.Lock()
        self._worker = None
        self._stopping = threading.Event()

    def register(self, name, func, min_interval, timeout=None):
        with self._state_lock:
            self._jobs[name] = Job(name, func, min_interval, timeout)

    def start(self):
        if self._worker is not None:
            return
        self._worker = threading.Thread(
            target=self._run_worker, name="job-queue", daemon=True
        )
        self._worker.start()

    def submit(self, name, force=False):
        """Queue a job. Never blocks on the job itself.

        Returns (accepted, reason, detail). `force` bypasses the min_interval
        gate but still refuses to queue a duplicate.
        """
        with self._state_lock:
            job = self._jobs.get(name)
            if job is None:
                return False, "unknown_job", f"no job named {name!r}"
            if name in self._pending:
                return False, ALREADY_QUEUED, "already waiting in the queue"
            if self._running == name:
                return False, RUNNING, "currently running"
            if not force:
                wait = job.seconds_until_eligible()
                if wait > 0:
                    job.skipped_early += 1
                    return (
                        False,
                        TOO_EARLY,
                        f"ran recently; eligible in {int(wait)}s",
                    )
            self._pending.add(name)
        # force travels with the entry: _execute re-checks the interval, and
        # without this a forced job would be queued and then skipped there.
        self._queue.put((name, force))
        return True, SUBMITTED, "queued"

    def _run_worker(self):
        while not self._stopping.is_set():
            try:
                name, force = self._queue.get(timeout=1)
            except queue_module.Empty:
                continue
            try:
                self._execute(name, force)
            finally:
                self._queue.task_done()

    def _execute(self, name, force=False):
        with self._state_lock:
            job = self._jobs.get(name)
            self._pending.discard(name)
            if job is None:
                return
            # Re-check here, not only in submit(): a job can sit in the queue
            # long enough for an earlier run to have satisfied the interval.
            wait = 0 if force else job.seconds_until_eligible()
            if wait > 0:
                job.skipped_early += 1
                print(f"[queue] skip {name}: eligible in {int(wait)}s")
                return
            self._running = name
            job.last_started_at = time.monotonic()

        print(f"[queue] start {name}")
        started = time.monotonic()
        try:
            self._call_with_timeout(job)
            job.last_error = None
            job.run_count += 1
            elapsed = time.monotonic() - started
            print(f"[queue] done {name} in {elapsed:.1f}s")
        except Exception as error:
            job.last_error = str(error)
            print(f"[queue] failed {name}: {error}")
        finally:
            with self._state_lock:
                # Interval counts from the end of a run, so a long job does not
                # immediately become eligible again.
                job.last_finished_at = time.monotonic()
                self._running = None

    def _call_with_timeout(self, job):
        """Run the job, giving up the wait after job.timeout seconds.

        The worker stops waiting, but the job's own thread keeps running: a
        blocked TDLib or MySQL call cannot be killed from outside. The point is
        that the queue keeps moving instead of wedging behind one stuck job.
        """
        if not job.timeout:
            job.func()
            return

        done = threading.Event()
        box = {}

        def _target():
            try:
                job.func()
            except Exception as error:
                box["error"] = error
            finally:
                done.set()

        thread = threading.Thread(
            target=_target, name=f"job-{job.name}", daemon=True
        )
        thread.start()
        if not done.wait(job.timeout):
            raise TimeoutError(
                f"{job.name} exceeded {job.timeout}s and was abandoned"
            )
        if "error" in box:
            raise box["error"]

    def status(self):
        with self._state_lock:
            now = time.monotonic()
            return {
                "running": self._running,
                "pending": sorted(self._pending),
                "jobs": {
                    name: {
                        "run_count": job.run_count,
                        "skipped_early": job.skipped_early,
                        "min_interval": job.min_interval,
                        "seconds_until_eligible": int(
                            job.seconds_until_eligible(now)
                        ),
                        "last_error": job.last_error,
                    }
                    for name, job in self._jobs.items()
                },
            }


# One queue per process, mirroring the single engine in app.Context.
job_queue = JobQueue()
