"""Job queue with two ways in: queued (the scheduler) and immediate (a person).

Every job used to take one shared `job_lock` directly on whatever thread asked
for it -- the scheduler thread, or a web thread coming in through
/api/job/*. A slow TDLib call therefore blocked web requests indefinitely, and
APScheduler's max_instances let repeat firings pile up behind the same lock.

Two paths now:

  * submit()  -- the scheduler's path. The job goes on a FIFO queue and one
                 worker thread runs it later. Deduped, and gated by
                 min_interval so a cron firing cannot run a job early.
  * run_now() -- a person's path, used by /api/job/*. The job runs
                 immediately and the caller gets its real return value.
                 min_interval does not apply: that gate paces the scheduler,
                 it is not there to overrule someone asking by hand.

Both paths share `_inflight`, so one job never runs twice at the same time
whichever door it came through -- the jobs share one TDLib client and one
database pool, and two concurrent copies would fight over both.
"""

import threading
import queue as queue_module
import time


# Outcomes reported back to callers.
SUBMITTED = "submitted"
ALREADY_QUEUED = "already_queued"
RUNNING = "running"
TOO_EARLY = "too_early"
RAN = "ran"
FAILED = "failed"
TIMED_OUT = "timed_out"
UNKNOWN_JOB = "unknown_job"


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
        remaining = self.min_interval - (now - self.last_finished_at)
        return remaining if remaining > 0 else 0


class JobQueue:
    def __init__(self):
        self._jobs = {}
        self._queue = queue_module.Queue()
        self._pending = set()
        # Jobs executing right now, whichever path started them.
        self._inflight = set()
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

    # ---- queued path (the scheduler) --------------------------------

    def submit(self, name, force=False):
        """Put a job on the queue. Never blocks on the job itself.

        Returns (accepted, reason, detail). `force` skips the min_interval
        gate but still refuses a duplicate.
        """
        with self._state_lock:
            job = self._jobs.get(name)
            if job is None:
                return False, UNKNOWN_JOB, f"no job named {name!r}"
            if name in self._pending:
                return False, ALREADY_QUEUED, "already waiting in the queue"
            if name in self._inflight:
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

    # ---- immediate path (a person) ----------------------------------

    def run_now(self, name):
        """Run a job right now and return what it returned.

        The job executes on this thread's behalf instead of being handed to
        the worker, so the caller waits for the real outcome. Refused only if
        that same job is already running, because a second copy would share
        the one TDLib client and the one database pool with the first.

        Returns (ok, reason, detail, result).
        """
        with self._state_lock:
            job = self._jobs.get(name)
            if job is None:
                return False, UNKNOWN_JOB, f"no job named {name!r}", None
            if name in self._inflight:
                return (
                    False,
                    RUNNING,
                    "already running; wait for it to finish",
                    None,
                )
            self._inflight.add(name)
            job.last_started_at = time.monotonic()

        print(f"[queue] run-now {name}")
        started = time.monotonic()
        try:
            result = self._invoke(job)
            job.last_error = None
            job.run_count += 1
            elapsed = time.monotonic() - started
            print(f"[queue] run-now done {name} in {elapsed:.1f}s")
            return True, RAN, f"ran in {elapsed:.1f}s", result
        except TimeoutError as error:
            job.last_error = str(error)
            print(f"[queue] run-now timed out {name}: {error}")
            return False, TIMED_OUT, str(error), None
        except Exception as error:
            job.last_error = str(error)
            print(f"[queue] run-now failed {name}: {error}")
            return False, FAILED, str(error), None

    # ---- worker ------------------------------------------------------

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
            if name in self._inflight:
                # A run_now() started it while this entry sat in the queue.
                print(f"[queue] skip {name}: already running")
                return
            # Re-check the interval here, not only in submit(): a job can sit
            # in the queue long enough for an earlier run to have satisfied it.
            wait = 0 if force else job.seconds_until_eligible()
            if wait > 0:
                job.skipped_early += 1
                print(f"[queue] skip {name}: eligible in {int(wait)}s")
                return
            self._inflight.add(name)
            job.last_started_at = time.monotonic()

        print(f"[queue] start {name}")
        started = time.monotonic()
        try:
            self._invoke(job)
            job.last_error = None
            job.run_count += 1
            print(f"[queue] done {name} in {time.monotonic() - started:.1f}s")
        except Exception as error:
            job.last_error = str(error)
            print(f"[queue] failed {name}: {error}")

    # ---- shared execution --------------------------------------------

    def _invoke(self, job):
        """Run job.func with a watchdog, and return its value.

        The function runs on a helper thread so the waiter can give up after
        job.timeout. Giving up does not stop the function -- a blocked TDLib
        or MySQL call cannot be killed from outside -- so the job stays marked
        in-flight until it really ends, and that is deliberate: it is what
        stops a second copy being started on top of a stuck one.
        """
        box = {}
        done = threading.Event()

        def _target():
            try:
                box["result"] = job.func()
            except Exception as error:
                box["error"] = error
            finally:
                self._finish(job.name)
                done.set()

        threading.Thread(
            target=_target, name=f"job-{job.name}", daemon=True
        ).start()

        # timeout=None waits indefinitely, which is what an unset timeout means.
        if not done.wait(job.timeout):
            raise TimeoutError(
                f"{job.name} exceeded {job.timeout}s and is still running"
            )
        if "error" in box:
            raise box["error"]
        return box.get("result")

    def _finish(self, name):
        """Mark a job finished. Runs on the job's own thread, always."""
        with self._state_lock:
            job = self._jobs.get(name)
            if job is not None:
                # The interval counts from the end of a run, so a long job
                # does not become eligible again the moment it stops.
                job.last_finished_at = time.monotonic()
            self._inflight.discard(name)

    def status(self):
        with self._state_lock:
            now = time.monotonic()
            return {
                "running": sorted(self._inflight),
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
