"""Periodic background jobs with database-lease leader election.

Each job has a lease row (`scheduler_leases`). Every process checks each job every few seconds:
it takes or renews the short lease with a conditional UPDATE (or an INSERT for a new job), and only
the holder may run the job - and only when it is due, judged by the shared `last_run_at`. So with
several API replicas a job runs on exactly one of them at its interval; if the holder dies, its
lease lapses within LEASE_TTL_S and another replica continues on the same schedule (no early
re-run, no long gap). A clean shutdown releases the leases at once. Jobs run in worker threads,
so the event loop (and WebSockets) never block on them.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Dict, List

from sqlalchemy import or_, update
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .db import iso, read_session, utcnow, write_tx
from .models import SchedulerLease
from .observability import METRICS

logger = logging.getLogger('trident.jobs')
HOLDER = f'{socket.gethostname()}:{os.getpid()}'


@dataclass
class Job:
    name: str
    every_s: float
    fn: Callable[[], object]
    initial_delay_s: float = 1.0


LEASE_TTL_S = 60          # must exceed the longest job run; renewed on every check
CHECK_EVERY_S = 10        # how often a process re-checks a slow job


def _acquire(job: str, ttl_s: float, every_s: float = 0.0) -> bool:
    """Take or renew the lease; True only if we hold it and the job is due."""
    now = utcnow()
    expires = now + timedelta(seconds=ttl_s)
    try:
        with write_tx() as s:
            n = s.execute(update(SchedulerLease).where(
                SchedulerLease.job == job,
                or_(SchedulerLease.holder == HOLDER, SchedulerLease.expires_at < now))
                .values(holder=HOLDER, expires_at=expires)).rowcount
            if n == 1:
                last = s.get(SchedulerLease, job).last_run_at
                return last is None or (now - last).total_seconds() >= every_s - 0.5
            if s.get(SchedulerLease, job) is None:
                s.add(SchedulerLease(job=job, holder=HOLDER, expires_at=expires))
                return True
            return False
    except IntegrityError:                    # another replica inserted the lease first
        return False


def _release() -> None:
    with write_tx() as s:
        s.execute(update(SchedulerLease).where(SchedulerLease.holder == HOLDER).values(expires_at=utcnow()))


def _record(job: str, status: str, success: bool = True) -> None:
    """last_run_at only moves on success: a failed run (e.g. a network error) is retried with backoff
    instead of waiting a whole interval."""
    with write_tx() as s:
        lease = s.get(SchedulerLease, job)
        if lease is not None and lease.holder == HOLDER:
            lease.last_status = status[:256]
            if success:
                lease.last_run_at = utcnow()


def lease_ttl(every_s: float) -> float:
    """Short for fast safety jobs (a dead holder is replaced within seconds), LEASE_TTL_S otherwise."""
    return min(LEASE_TTL_S, max(10.0, every_s * 10))


class Scheduler:
    def __init__(self, jobs: List[Job]):
        self.jobs = jobs
        self.tasks: List[asyncio.Task] = []

    async def _loop(self, job: Job) -> None:
        await asyncio.sleep(job.initial_delay_s)
        check = min(job.every_s, CHECK_EVERY_S)
        backoff, retry_at = 0.0, 0.0
        while True:
            t0 = time.perf_counter()
            try:
                if time.monotonic() >= retry_at and await asyncio.to_thread(_acquire, job.name, lease_ttl(job.every_s),
                                                                            job.every_s):
                    result = await asyncio.to_thread(job.fn)
                    await asyncio.to_thread(_record, job.name, f'ok: {result}')
                    METRICS.inc('job_runs_total', job=job.name, result='ok')
                    METRICS.observe('job_seconds', time.perf_counter() - t0, job=job.name)
                    backoff = 0.0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception('job %s failed', job.name)
                METRICS.inc('job_runs_total', job=job.name, result='error')
                backoff = min(300.0, max(5.0, backoff * 2))       # 5, 10, 20 ... 300 s
                retry_at = time.monotonic() + min(backoff, job.every_s)
                try:
                    await asyncio.to_thread(_record, job.name, f'error: {type(e).__name__}: {e}', False)
                except Exception:
                    pass
            await asyncio.sleep(max(0.5, check - (time.perf_counter() - t0)))

    def start(self) -> None:
        self.tasks = [asyncio.create_task(self._loop(j), name=f'job:{j.name}') for j in self.jobs]
        logger.info('scheduler started (%s): %s', HOLDER, ', '.join(j.name for j in self.jobs))

    async def stop(self) -> None:
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        try:
            await asyncio.to_thread(_release)       # let another replica take over immediately
        except Exception:
            logger.warning('could not release scheduler leases', exc_info=True)


def default_jobs() -> List[Job]:
    from .services import alerts, auth, public_data, rov, sos, telemetry
    from .services.weather import WEATHER
    s = get_settings()
    return [
        Job('device_liveness', 15, lambda: telemetry.mark_offline(s.device_offline_s)),
        Job('sos_auto_triage', 10, lambda: sos.auto_triage(s.auto_assign_max_priority), initial_delay_s=3),
        Job('alert_escalation', 30, lambda: alerts.escalate(s.alert_escalate_s)),
        Job('rov_simulation', 1, rov.tick),
        Job('weather_refresh', 30 * 60, WEATHER.refresh, initial_delay_s=2),
        Job('public_data', 3 * 3600, public_data.refresh_rivers, initial_delay_s=5),
        Job('retention', 6 * 3600, lambda: (telemetry.retention(), auth.purge_tokens(), rov.prune_samples()),
            initial_delay_s=60),
    ]


def lease_status() -> List[Dict]:
    with read_session() as s:
        from sqlalchemy import select
        return [{'job': l.job, 'holder': l.holder, 'expires_at': iso(l.expires_at), 'last_run_at': iso(l.last_run_at),
                 'last_status': l.last_status} for l in s.scalars(select(SchedulerLease)).all()]
