"""The worker: claim a job, run it in a child interpreter with a heartbeat, record the outcome atomically.

`run_forever()` serves `sutradhar worker` (airgap: its own container) and the embedded worker thread of the
demo API. `run_once()` runs a single job synchronously (CLI and tests).
"""

from __future__ import annotations

import json
import logging
import os
import queue
import socket
import subprocess  # nosec B404 - runs only our own job module, fixed argv, no shell
import sys
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from sutradhar_api import offline_guard
from sutradhar_api.config import Settings
from sutradhar_api.db import Database
from sutradhar_api.jobs import maintenance
from sutradhar_api.jobs.handlers import HANDLERS
from sutradhar_api.jobs.queue import Claim, add_event, claim, heartbeat, mark_finished, stale_jobs
from sutradhar_api.models import Job

log = logging.getLogger("sutradhar.worker")
HEARTBEAT_S = 5.0
PROGRESS_EVERY_S = 0.5
MAINTENANCE_EVERY_S = 30.0


def _read_lines(stream: Any, out: queue.Queue[dict[str, Any] | None]) -> None:
    """Forward protocol lines; anything that is not a JSON object is ignored. `None` marks end of stream."""
    try:
        for line in stream:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict):
                out.put(message)
    finally:
        out.put(None)


@dataclass
class Outcome:
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class Worker:
    def __init__(self, settings: Settings, db: Database, *, concurrency: int | None = None) -> None:
        self.settings = settings
        self.db = db
        self.concurrency = concurrency or settings.worker_concurrency
        self.worker_id = f"{socket.gethostname()[:32]}:{os.getpid()}"
        self.running = threading.Event()

    def _child_config(self) -> dict[str, Any]:
        return {
            "guard_mode": self.settings.guard_mode,
            "allow_hosts": [*self.settings.offline_allow_hosts, self.settings.db_host or ""],
            "data_dir": str(self.settings.data_dir),
            "threads": self.settings.engine_threads,
        }

    # ── one job ──────────────────────────────────────────────────────────────────────────────────────────
    def run_once(self) -> bool:
        claimed = claim(self.db, self.worker_id)
        if claimed is None:
            return False
        self.execute(claimed, threading.Event())
        return True

    def execute(self, job: Claim, stop: threading.Event) -> None:
        handler = HANDLERS.get(job.kind)
        if handler is None:
            self._finish(job, Outcome("failed", error=f"no handler for job kind {job.kind!r}"))
            return
        outcome = self._supervise(job, stop)
        self._finish(job, outcome)

    def _child_env(self) -> dict[str, str]:
        """Least privilege: the job process gets no database URL and no secrets."""
        drop = {"DATABASE_URL", "MIGRATION_DATABASE_URL", "JWT_SECRET", "DEMO_ADMIN_PASSWORD"}
        return {k: v for k, v in os.environ.items() if k.upper() not in drop}

    def _supervise(self, job: Claim, stop: threading.Event) -> Outcome:
        proc = subprocess.Popen(  # nosec B603  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", "sutradhar_api.jobs.child"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=self._child_env(),
        )
        if proc.stdin is None or proc.stdout is None:
            raise RuntimeError("job process pipes were not created")
        proc.stdin.write(
            json.dumps({"kind": job.kind, "payload": job.payload, "config": self._child_config()})
        )
        proc.stdin.close()
        messages: queue.Queue[dict[str, Any] | None] = queue.Queue()
        reader = threading.Thread(target=_read_lines, args=(proc.stdout, messages), daemon=True)
        reader.start()
        deadline = time.monotonic() + self.settings.job_timeout_s
        last_beat = last_progress = time.monotonic()
        last_stage = ""
        outcome: Outcome | None = None
        try:
            while True:
                try:
                    message = messages.get(timeout=0.25)
                except queue.Empty:
                    message = {}
                if message is None:
                    break
                kind = message.get("t")
                if kind == "progress":
                    stage, pct = str(message["stage"]), float(message["pct"])
                    now = time.monotonic()
                    if stage != last_stage or now - last_progress >= PROGRESS_EVERY_S or pct >= 1:
                        self._progress(job, stage, pct, str(message.get("message", "")))
                        last_stage, last_progress = stage, now
                elif kind == "result":
                    outcome = Outcome("succeeded", result=message["result"])
                elif kind == "error":
                    outcome = Outcome("failed", error=str(message["error"]))
                now = time.monotonic()
                if now - last_beat >= HEARTBEAT_S:
                    owner, cancel = heartbeat(self.db, job.job_id, job.token)
                    last_beat = now
                    if not owner:
                        log.warning("job %s: lost ownership; stopping", job.job_id)
                        return Outcome("lost")
                    if cancel:
                        return Outcome("cancelled", error="cancelled by user")
                if stop.is_set():
                    return Outcome("failed", error="worker shutting down")
                if now > deadline:
                    return Outcome("failed", error=f"timed out after {self.settings.job_timeout_s} s")
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            reader.join(5)
        if outcome is None:
            return Outcome(
                "failed", error=f"the job process ended unexpectedly (exit code {proc.returncode})"
            )
        return outcome

    def _progress(self, job: Claim, stage: str, pct: float, text: str) -> None:
        with self.db.write() as session:
            add_event(
                session,
                job.job_id,
                "job.progress",
                {"job_id": job.job_id, "stage": stage, "pct": pct, "message": text},
            )
            HANDLERS[job.kind].on_progress(session, job, stage)
            session.commit()

    def _finish(self, job: Claim, outcome: Outcome) -> None:
        if outcome.status == "lost":
            return
        handler = HANDLERS.get(job.kind)
        if outcome.status == "succeeded" and handler is not None and outcome.result is not None:
            try:
                with self.db.write() as session:
                    summary = handler.on_success(session, job, outcome.result, self.settings.data_dir)
                    if not mark_finished(session, job.job_id, job.token, status="succeeded", result=summary):
                        session.rollback()
                        return
                    add_event(session, job.job_id, "job.completed", {"job_id": job.job_id, "result": summary})
                    session.commit()
                    return
            except Exception as exc:
                log.exception("job %s: recording the result failed", job.job_id)
                outcome = Outcome("failed", error=f"could not record the result: {type(exc).__name__}")
        error = outcome.error or "failed"
        with self.db.write() as session:
            if handler is not None:
                handler.on_failure(session, job.payload, error)
            status = "cancelled" if outcome.status == "cancelled" else "failed"
            if not mark_finished(session, job.job_id, job.token, status=status, error=error):
                session.rollback()
                return
            add_event(session, job.job_id, f"job.{status}", {"job_id": job.job_id, "error": error})
            session.commit()

    # ── the loop ─────────────────────────────────────────────────────────────────────────────────────────
    def maintain(self) -> None:
        with self.db.write() as session:
            for job in stale_jobs(session):
                self._rescue(session, job)
            session.commit()
        maintenance.purge_expired(self.db, self.settings)

    def _rescue(self, session: Any, job: Job) -> None:
        if job.attempts < job.max_attempts:
            job.status, job.locked_by = "queued", None
            add_event(
                session, job.id, "job.requeued", {"job_id": job.id, "reason": "worker stopped responding"}
            )
            return
        job.status, job.locked_by, job.error = "failed", None, "the worker stopped responding"
        handler = HANDLERS.get(job.kind)
        if handler is not None:
            handler.on_failure(session, job.payload, job.error)
        add_event(session, job.id, "job.failed", {"job_id": job.id, "error": job.error})

    def run_forever(self, stop: threading.Event) -> None:
        offline_guard.install(
            self.settings.guard_mode, [*self.settings.offline_allow_hosts, self.settings.db_host]
        )
        self.running.set()
        active: set[Future[None]] = set()
        last_maintenance = 0.0
        try:
            with ThreadPoolExecutor(max_workers=self.concurrency, thread_name_prefix="job") as pool:
                while not stop.is_set():
                    if time.monotonic() - last_maintenance >= MAINTENANCE_EVERY_S:
                        self._safely(self.maintain)
                        last_maintenance = time.monotonic()
                    active = {f for f in active if not f.done()}
                    if len(active) < self.concurrency:
                        claimed = self._safely(lambda: claim(self.db, self.worker_id))
                        if claimed is not None:
                            active.add(pool.submit(self._safely, lambda c=claimed: self.execute(c, stop)))
                            continue
                    stop.wait(0.5)
        finally:
            self.running.clear()

    @staticmethod
    def _safely(fn: Any) -> Any:
        try:
            return fn()
        except Exception:
            log.exception("worker step failed; continuing")
            time.sleep(1)
            return None
