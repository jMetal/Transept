"""Series of runs: the same request with consecutive seeds, launched a few at a time.

A detached process launches the runs, so that a series survives the browser and Transept, like a
single run. Everything about a series is in files: `<runs-root>/series/<dataset>/<series-id>/` holds
what it asks for, the PID of that process, its log and the cancellation mark. Each run is an
ordinary run, called `<series-id>_seed_<seed>`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path

from transept import runner, runs

SERIES_FILE = "series.json"
PID_FILE = "pid.txt"
LOG_FILE = "log.txt"
CANCELLED_FILE = "cancelled"
MAX_SEED = 2**31 - 1
POLL_SECONDS = 1.0


class SeriesState(Enum):
    """State of a series."""

    RUNNING = "running"
    FINISHED = "finished"
    FINISHED_WITH_PROBLEMS = "finished, with problems"
    CANCELLED = "cancelled"
    STOPPED = "stopped before finishing"


QUEUED = "queued"
NOT_STARTED = "not started"
DELETED = "deleted"


@dataclass(slots=True, frozen=True)
class Series:
    """A series of runs.

    Attributes:
        dataset: Dataset name.
        series_id: Its identifier, unique within the dataset.
        directory: Where its files are.
        requests: One request per run.
        parallel: How many runs may be active at a time.
        jar: The jar that runs them.
        data_root: The data directory.
        runs_root: The root of the runs.
    """

    dataset: str
    series_id: str
    directory: Path
    requests: tuple[runner.RunRequest, ...]
    parallel: int
    jar: str
    data_root: str
    runs_root: Path

    @property
    def key(self) -> str:
        """Returns a label that identifies the series."""
        return f"{self.dataset} / {self.series_id}"


@dataclass(slots=True, frozen=True)
class Member:
    """A run of a series, which may not have started.

    Attributes:
        seed: Its random seed.
        run: The run.
        state: The value of its state, or queued, not started or deleted.
    """

    seed: int
    run: runs.Run
    state: str


def member_requests(request: runner.RunRequest, count: int) -> tuple[runner.RunRequest, ...]:
    """Returns the requests of a series; `request.seed` is the seed of the first run."""
    return tuple(
        replace(request, run_id=f"{request.run_id}_seed_{seed}", seed=seed)
        for seed in range(request.seed, request.seed + count)
    )


def validate(request: runner.RunRequest, count: int, parallel: int) -> list[str]:
    """Lists the problems of a series, besides those of its request."""
    found = []
    if count < 2:
        found.append("A series needs at least two runs.")
    if parallel < 1:
        found.append("At least one run must be active at a time.")
    if request.seed + count - 1 > MAX_SEED:
        found.append(f"The seeds of the series must not exceed {MAX_SEED}.")
    return found


def series_directory(runs_root: Path, dataset: str, series_id: str) -> Path:
    """Returns the directory of a series."""
    return runs_root / "series" / dataset / series_id


def load(directory: Path) -> Series:
    """Reads a series from its directory."""
    saved = json.loads((directory / SERIES_FILE).read_text(encoding="utf-8"))
    return Series(
        saved["dataset"],
        saved["series_id"],
        directory,
        tuple(runner.request_from_dict(values) for values in saved["requests"]),
        saved["parallel"],
        saved["jar"],
        saved["data_root"],
        Path(saved["runs_root"]),
    )


def _is_active(directory: Path) -> bool:
    return runner.is_alive(runner.read_pid(directory))


def _is_cancelled(directory: Path) -> bool:
    return (directory / CANCELLED_FILE).is_file()


def _run_of(series: Series, request: runner.RunRequest) -> runs.Run:
    return runs.run_of(series.runs_root, series.dataset, request.run_id)


def _exists(run: runs.Run) -> bool:
    return run.results.exists() or run.job.exists()


def members(series: Series) -> list[Member]:
    """Returns the runs of a series with their states."""
    active = _is_active(series.directory) and not _is_cancelled(series.directory)
    found = []
    for request in series.requests:
        run = _run_of(series, request)
        if _exists(run):
            state = runs.state(run).value
        elif (series.directory / f"started_{request.seed}").is_file():
            state = DELETED
        else:
            state = QUEUED if active else NOT_STARTED
        found.append(Member(request.seed, run, state))
    return found


def state(series: Series) -> SeriesState:
    """Returns the state of a series: its process, or else what became of its runs."""
    if _is_active(series.directory):
        return SeriesState.RUNNING
    states = [member.state for member in members(series)]
    if runs.RunState.RUNNING.value in states:
        return SeriesState.RUNNING
    if _is_cancelled(series.directory):
        return SeriesState.CANCELLED
    if NOT_STARTED in states:
        return SeriesState.STOPPED
    if all(value == runs.RunState.FINISHED.value for value in states):
        return SeriesState.FINISHED
    return SeriesState.FINISHED_WITH_PROBLEMS


def launch(
    request: runner.RunRequest, count: int, parallel: int, jar: str, data_root: str, runs_root: Path
) -> Series:
    """Starts a series in the background; `request.run_id` is the identifier of the series.

    Raises:
        FileExistsError: If the identifier or one of its runs is already used in the dataset.
    """
    directory = series_directory(runs_root, request.dataset, request.run_id)
    requests = member_requests(request, count)
    if directory.exists():
        raise FileExistsError(f"Series '{request.run_id}' already exists in {request.dataset}")
    for member in requests:
        if _exists(runs.run_of(runs_root, request.dataset, member.run_id)):
            raise FileExistsError(f"Run '{member.run_id}' already exists in {request.dataset}")
    directory.mkdir(parents=True)
    saved = {
        "dataset": request.dataset,
        "series_id": request.run_id,
        "requests": [asdict(member) for member in requests],
        "parallel": parallel,
        "jar": str(jar),
        "data_root": str(data_root),
        "runs_root": str(runs_root),
    }
    (directory / SERIES_FILE).write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    with (directory / LOG_FILE).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "transept.series", str(directory)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (directory / PID_FILE).write_text(f"{process.pid}\n", encoding="utf-8")
    threading.Thread(target=process.wait, daemon=True).start()
    return load(directory)


def cancel(series: Series) -> None:
    """Stops launching runs and cancels the active ones."""
    (series.directory / CANCELLED_FILE).write_text("cancelled by the user\n", encoding="utf-8")
    for member in members(series):
        if member.state == runs.RunState.RUNNING.value:
            runner.cancel(member.run.job)


def drive(series: Series, poll_seconds: float = POLL_SECONDS) -> None:
    """Launches the runs of a series, keeping at most `parallel` active, until none is left."""
    pending = deque(series.requests)
    active: list[runs.Run] = []
    while True:
        active = [run for run in active if runs.state(run) == runs.RunState.RUNNING]
        if _is_cancelled(series.directory):
            return
        while pending and len(active) < series.parallel:
            request = pending.popleft()
            try:
                job = runner.launch(request, series.jar, series.data_root, series.runs_root)
            except FileExistsError as error:  # someone used the identifier in the meantime
                print(error, flush=True)
                continue
            (series.directory / f"started_{request.seed}").touch()
            active.append(_run_of(series, request))
            if _is_cancelled(series.directory):  # cancelled while it was being launched
                runner.cancel(job)
                return
        if not pending and not active:
            return
        time.sleep(poll_seconds)


def list_series(runs_root: Path) -> list[Series]:
    """Returns the series with at least one run left, newest first."""
    found = []
    for path in sorted(
        (runs_root / "series").glob(f"*/*/{SERIES_FILE}"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        series = load(path.parent)
        if _is_active(series.directory) or any(
            member.state not in (DELETED, NOT_STARTED) for member in members(series)
        ):
            found.append(series)
    return found


def all_series(runs_root: Path) -> list[Series]:
    """Returns every series, also those whose runs were all deleted."""
    paths = (runs_root / "series").glob(f"*/*/{SERIES_FILE}")
    return [load(path.parent) for path in sorted(paths)]


def move_to_trash(chosen: Series) -> int:
    """Moves the runs of a series to the trash and returns how many there were.

    Raises:
        ValueError: If the series is still running; cancel it first.
    """
    if state(chosen) == SeriesState.RUNNING:
        raise ValueError(f"{chosen.key} is still running: cancel it first")
    existing = [run for run in (_run_of(chosen, r) for r in chosen.requests) if _exists(run)]
    for run in existing:
        runs.move_to_trash(chosen.runs_root, run)
    return len(existing)


def trashed_runs(chosen: Series) -> list[runs.TrashedRun]:
    """Returns the runs of a series that are in the trash."""
    identifiers = {request.run_id for request in chosen.requests}
    return [
        item
        for item in runs.list_trash(chosen.runs_root)
        if item.dataset == chosen.dataset and item.run_id in identifiers
    ]


def forget_deleted(runs_root: Path) -> None:
    """Removes the files of the series with no run left, neither in use nor in the trash."""
    for item in all_series(runs_root):
        if (
            not _is_active(item.directory)
            and not any(_exists(_run_of(item, request)) for request in item.requests)
            and not trashed_runs(item)
        ):
            shutil.rmtree(item.directory, ignore_errors=True)


def series_of_runs(runs_root: Path) -> dict[tuple[str, str], str]:
    """Returns the series of every run that belongs to one, by dataset and run identifier."""
    return {
        (series.dataset, request.run_id): series.series_id
        for series in list_series(runs_root)
        for request in series.requests
    }


if __name__ == "__main__":
    drive(load(Path(sys.argv[1])))
