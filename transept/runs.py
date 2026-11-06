"""The runs of Transept: their state, progress, results and errors."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import pandas as pd

from transept import runner

OBJECTIVES = ("SOPwTP", "lDDT")


class RunState(Enum):
    """State of a run."""

    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


@dataclass(slots=True, frozen=True)
class Run:
    """A run, launched from Transept or found in its results directory.

    Attributes:
        dataset: Dataset name.
        run_id: Identifier of the run.
        results: Directory where the tool writes the results (it may not exist yet).
        job: Directory where Transept keeps its files about the run (it may not exist).
    """

    dataset: str
    run_id: str
    results: Path
    job: Path

    @property
    def key(self) -> str:
        """Returns a label that identifies the run."""
        return f"{self.dataset} / {self.run_id}"


def run_of(runs_root: Path, dataset: str, run_id: str) -> Run:
    """Returns the run with this dataset and identifier."""
    return Run(
        dataset,
        run_id,
        runner.run_directory(runs_root, dataset, run_id),
        runner.job_directory(runs_root, dataset, run_id),
    )


def list_runs(runs_root: Path) -> list[Run]:
    """Returns every run, from the job and results directories, newest first."""
    found: dict[tuple[str, str], Run] = {}
    for parent in (runs_root / "ejecuciones", runs_root / "jobs"):
        if parent.is_dir():
            for directory in parent.glob("*/*"):
                if directory.is_dir():
                    key = (directory.parent.name, directory.name)
                    found[key] = run_of(runs_root, *key)
    return sorted(found.values(), key=_last_change, reverse=True)


def _last_change(run: Run) -> float:
    times = [path.stat().st_mtime for path in (run.results, run.job) if path.exists()]
    return max(times, default=0.0)


def state(run: Run) -> RunState:
    """Returns the state of a run.

    The tool writes metadata.json last, and error.json if it fails. A run whose process is gone
    without either was cancelled (if Transept marked it) or interrupted.
    """
    if (run.results / "error.json").is_file():
        return RunState.FAILED
    if (run.results / "metadata.json").is_file():
        return RunState.FINISHED
    if (run.job / runner.CANCELLED_FILE).is_file():
        return RunState.CANCELLED
    if runner.is_alive(runner.read_pid(run.job)):
        return RunState.RUNNING
    if run.job.is_dir() and not run.results.is_dir():
        return RunState.FAILED  # the process ended before creating its directory
    return RunState.INTERRUPTED


def read_json(path: Path) -> dict | None:
    """Reads a JSON file, or returns None if it does not exist."""
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def config(run: Run) -> dict:
    """Returns the configuration of a run: config.json, or the request saved by Transept."""
    saved = read_json(run.results / "config.json")
    if saved is not None:
        return saved
    request = runner.read_request(run.job)
    if request is None:
        return {}
    return {
        "dataset": request.dataset,
        "algorithmType": request.algorithm,
        "maxEvaluations": request.max_evaluations,
        "populationSize": request.population_size,
        "seedMethods": list(request.seeds),
    }


def metadata(run: Run) -> dict | None:
    """Returns metadata.json of a finished run, or None."""
    return read_json(run.results / "metadata.json")


def error_message(run: Run) -> str | None:
    """Explains why a run failed: the message of error.json, or the end of the log."""
    error = read_json(run.results / "error.json")
    if error is not None:
        return f"{error.get('type', 'Error')}: {error.get('message', '')}"
    log = run.job / runner.LOG_FILE
    if log.is_file():
        lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        return "\n".join(lines[-15:]) or None
    return None


def progress(run: Run) -> pd.DataFrame:
    """Returns the progress records: evaluations, elapsed seconds and the best of each objective
    (one column per objective of the run, in the order of FUN.csv)."""
    path = run.results / "progress.jsonl"
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                row = {"evaluations": record["evaluations"], "seconds": record["elapsedMs"] / 1000}
                row.update(record.get("best", {}))
                rows.append(row)
    names = list(rows[0])[2:] if rows else list(objective_names(run))
    return pd.DataFrame(rows, columns=["evaluations", "seconds", *names])


def objective_names(run: Run) -> tuple[str, ...]:
    """Returns the objectives of a finished run, in the order of FUN.csv.

    Runs written before the tool recorded them used the default formulation.
    """
    names = (metadata(run) or {}).get("objectives")
    return tuple(names) if names else OBJECTIVES


def has_default_objectives(run: Run) -> bool:
    """Whether the run optimised SOPwTP and lDDT, the only formulation Transept analyses."""
    return objective_names(run) == OBJECTIVES


def objective_values(run: Run) -> pd.DataFrame:
    """Returns FUN.csv: one row per solution and one column per objective (higher is better)."""
    path = run.results / "FUN.csv"
    names = list(objective_names(run))
    if not path.is_file():
        return pd.DataFrame(columns=names)
    return pd.read_csv(path, header=None, names=names)


def alignment_file(run: Run, row: int) -> Path:
    """Returns the alignment of a row of FUN.csv."""
    return run.results / f"MSASol{row}.fasta"


TRASH_MANIFEST = "trashed.json"


@dataclass(slots=True, frozen=True)
class TrashedRun:
    """A run moved to the trash.

    Attributes:
        dataset: Dataset name.
        run_id: Identifier of the run.
        deleted_at: When it was moved to the trash (ISO 8601).
        path: Directory of the trash that holds its files.
    """

    dataset: str
    run_id: str
    deleted_at: str
    path: Path

    @property
    def key(self) -> str:
        """Returns a label that identifies the run."""
        return f"{self.dataset} / {self.run_id}"


def trash_root(runs_root: Path) -> Path:
    """Returns the directory of the trash."""
    return runs_root / "trash"


def move_to_trash(runs_root: Path, run: Run) -> Path:
    """Moves the results and the job files of a run to the trash.

    Raises:
        ValueError: If the run is still running; cancel it first.
    """
    if state(run) == RunState.RUNNING:
        raise ValueError(f"{run.key} is still running: cancel it first")
    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = trash_root(runs_root) / f"{stamp}_{run.dataset}_{run.run_id}"
    target.mkdir(parents=True)
    for name, source in (("ejecuciones", run.results), ("jobs", run.job)):
        if source.exists():
            shutil.move(str(source), str(target / name))
    manifest = {"dataset": run.dataset, "run_id": run.run_id, "deletedAt": deleted_at}
    (target / TRASH_MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def list_trash(runs_root: Path) -> list[TrashedRun]:
    """Returns the runs in the trash, most recently deleted first."""
    found = []
    root = trash_root(runs_root)
    if root.is_dir():
        for directory in root.iterdir():
            manifest = read_json(directory / TRASH_MANIFEST)
            if manifest:
                found.append(
                    TrashedRun(
                        manifest["dataset"], manifest["run_id"], manifest["deletedAt"], directory
                    )
                )
    return sorted(found, key=lambda item: item.path.name, reverse=True)


def restore(runs_root: Path, trashed: TrashedRun) -> Run:
    """Moves a run back from the trash.

    Raises:
        FileExistsError: If a run with the same dataset and identifier exists again.
    """
    run = run_of(runs_root, trashed.dataset, trashed.run_id)
    if run.results.exists() or run.job.exists():
        raise FileExistsError(f"{run.key} exists again: rename or delete it first")
    for name, target in (("ejecuciones", run.results), ("jobs", run.job)):
        source = trashed.path / name
        if source.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
    shutil.rmtree(trashed.path)
    return run


def empty_trash(runs_root: Path) -> int:
    """Deletes every run in the trash for good and returns how many there were."""
    trashed = list_trash(runs_root)
    shutil.rmtree(trash_root(runs_root), ignore_errors=True)
    return len(trashed)


def finished_runs_of(runs_root: Path, dataset: str, data_root: str) -> list[Run]:
    """Returns the finished runs of a dataset of a data directory.

    Runs that did not record their data directory count for every dataset with their name.
    """
    found = []
    for run in list_runs(runs_root):
        if run.dataset != dataset or state(run) != RunState.FINISHED:
            continue
        recorded = config(run).get("dataRoot")
        if not recorded or Path(recorded).resolve() == Path(data_root).resolve():
            found.append(run)
    return found
