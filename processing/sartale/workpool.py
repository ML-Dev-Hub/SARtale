"""Bounded concurrency for lakes-fetch (worker processes) and lakes-check (threads), with the sequential run's output.

lakes-fetch runs in processes, not threads: h5py holds one global lock across every HDF5 call, and the range reads of
a remote window happen inside those calls (HDF5 calls back into `remote.RangeFile.readinto`), so threads reading
windows would wait on one another and fetch no faster. Each worker process has its own h5py, its own HTTP session
(`requests.Session`, which takes the Earthdata login from ~/.netrc like the sequential run's) and, through
`demmask.set_locks`, locks it shares with the other workers for the DEM files that several passes of a lake write.

What a worker prints is captured and handed back with its result; the caller prints it in the sequential order. Only
stdout is: warnings that h5py, GDAL or `warnings` write to stderr still reach the console as they happen.

Each worker marks in shared memory (`_STATE`, one byte per task) when it starts and ends a task, so that when a worker
process dies and breaks the pool, the caller knows which tasks were running then (`run_pipeline._ParallelFetch`).
"""
from __future__ import annotations

import contextlib
import io
import sys
import threading

_SESSION = None  # the worker process's HTTP session (`init_fetch_worker`)
_STATE = None  # per task: 0 waiting, 1 started, 2 ended (a multiprocessing RawArray shared with the caller)
STARTED, ENDED = 1, 2


def fetch_one(fetch, lake, p, out, session, stats: dict) -> tuple[int, str | None]:
    """Fetch one pass as lakes-fetch always has: (windows cached, None), or (0, failure note) when it raises. The note
    carries no URL (it is signed)."""
    try:
        return len(fetch(lake, [p], out, session, stats)), None
    except Exception as e:  # noqa: BLE001 - keep going; the summary lists it
        return 0, f"{lake.id} {p.date} {p.key}: {type(e).__name__}"


def init_fetch_worker(session_factory, dem_locks, state=None) -> None:
    """Set up a fetch worker process: one HTTP session for every pass it fetches, the shared DEM-file locks and the
    shared task marks."""
    from sartale import demmask

    global _SESSION, _STATE
    _SESSION = session_factory()
    _STATE = state
    demmask.set_locks(dem_locks)


def fetch_group(fetch, lake, passes, out, task: int | None = None) -> list[tuple[int, str | None, dict, str]]:
    """In a worker process: fetch `passes` (those of one lake that share one cache file) one after the other, as the
    sequential run would. Per pass: (windows cached, failure note or None, stats, what it printed). `task` is this
    group's slot in the shared marks."""
    if _STATE is not None and task is not None:
        _STATE[task] = STARTED
    results = []
    for p in passes:
        stats: dict = {}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            n, note = fetch_one(fetch, lake, p, out, _SESSION, stats)
        results.append((n, note, stats, buf.getvalue()))
    if _STATE is not None and task is not None:
        _STATE[task] = ENDED
    return results


class ThreadStdout(io.TextIOBase):
    """A stdout that sends what a thread prints to that thread's buffer (`capture`) and the rest to `real`, so the
    log lines of lakes checked at the same time can be printed one lake after the other."""

    def __init__(self, real):
        self.real, self.local = real, threading.local()

    def write(self, s):
        buf = getattr(self.local, "buf", None)
        return (buf if buf is not None else self.real).write(s)

    def flush(self):
        if getattr(self.local, "buf", None) is None:
            self.real.flush()

    def fileno(self):
        return self.real.fileno()

    @property
    def encoding(self):
        return getattr(self.real, "encoding", "utf-8")

    @contextlib.contextmanager
    def capture(self):
        self.local.buf = io.StringIO()
        try:
            yield self.local.buf
        finally:
            self.local.buf = None


@contextlib.contextmanager
def thread_stdout():
    """Install a `ThreadStdout` for the duration of the block (yielded)."""
    real = sys.stdout
    router = ThreadStdout(real)
    sys.stdout = router
    try:
        yield router
    finally:
        sys.stdout = real
