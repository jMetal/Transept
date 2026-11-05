"""Internal seeds of a dataset computed in advance with the `seeds` command of the tool.

The tool writes them to `<runs-root>/internal_seeds/<dataset>/` with a `manifest.tsv`, and the runs
with `--seeds internal` read them from there. The studio launches the command in the background
and only looks at the files to tell whether they are ready or being computed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from transept import runner, settings

NAME = "internal"
DIRECTORY = "internal_seeds"
MANIFEST = "manifest.tsv"
PID_SUFFIX = ".pid"
LOG_SUFFIX = ".log"


def directory(runs_root: Path, dataset: str) -> Path:
    """Returns the directory of the internal seeds of a dataset."""
    return runs_root / DIRECTORY / dataset


def ready(runs_root: Path, dataset: str) -> int:
    """Returns how many internal seeds of the dataset are computed in advance (0 if none).

    The tool checks that they match the data before using them; Transept only counts them.
    """
    manifest = directory(runs_root, dataset) / MANIFEST
    if not manifest.is_file():
        return 0
    lines = manifest.read_text(encoding="utf-8").splitlines()
    return sum(1 for line in lines if line.startswith("seed\t"))


def computing(runs_root: Path, dataset: str) -> bool:
    """Whether Transept launched the computation of the dataset's seeds and it still runs."""
    pid_file = runs_root / DIRECTORY / f"{dataset}{PID_SUFFIX}"
    if not pid_file.is_file():
        return False
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return False
    return runner.is_alive(pid)


def command(jar: str, data_root: str, runs_root: Path, dataset: str) -> list[str]:
    """Returns the command that computes the internal seeds of a dataset."""
    return [
        settings.java_command(), "-jar", str(jar), "seeds",
        "--data-root", str(data_root),
        "--datasets", dataset,
        "--output-root", str(runs_root),
    ]  # fmt: skip


def launch(jar: str, data_root: str, runs_root: Path, dataset: str) -> None:
    """Starts computing the internal seeds of a dataset in the background."""
    root = runs_root / DIRECTORY
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"{dataset}{LOG_SUFFIX}").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command(jar, data_root, runs_root, dataset),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (root / f"{dataset}{PID_SUFFIX}").write_text(f"{process.pid}\n", encoding="utf-8")
