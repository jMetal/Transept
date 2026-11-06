"""Fixtures: an isolated Transept home, a tiny data directory and runs in every state."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

from transept import runner, settings

DATA = Path(__file__).parent / "data"

TOPOLOGY = """>p1 | TM
ACDEFGHIK
OOMMMMOOO
>p2 | TM
ACDEGHIK
OOMMMOOO
>p3 | TM
ACEFGHIK
OOMMMOOO
"""

ALIGNMENTS = {
    "mafft": ["ACDEFGHIK", "ACDE-GHIK", "AC-EFGHIK"],
    "kalign": ["ACDEFGHIK", "ACD-EGHIK", "A-CEFGHIK"],
    "caretta": ["ACDEFGHIK-", "-ACDEGHIK-", "--ACEFGHIK"],
    "broken": ["ACDEFGHIK", "ACDE-GHIW", "AC-EFGHIK"],
}


@pytest.fixture
def transept_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv(settings.HOME_VARIABLE, str(home))
    monkeypatch.setattr(settings, "EXAMPLES", tmp_path / "no-examples")
    return home


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "GPCRdb"
    (root / "sequences" / "tmregions").mkdir(parents=True)
    (root / "sequences" / "tmregions" / "toy_predicted_topologies.3line").write_text(TOPOLOGY)
    (root / "precomputed" / "toy").mkdir(parents=True)
    for tool, rows in ALIGNMENTS.items():
        text = "".join(f">p{index + 1}\n{row}\n" for index, row in enumerate(rows))
        (root / "precomputed" / "toy" / f"{tool}_toy.fasta").write_text(text)
    (root / "precomputed" / "toy" / "baselines.csv").write_text("not a seed\n")
    (root / "distances" / "toy").mkdir(parents=True)
    for protein in ("p1", "p2"):  # p3 has no structure
        (root / "distances" / "toy" / f"{protein}_D.csv").write_text("0\n")
        (root / "distances" / "toy" / f"{protein}_idx.csv").write_text("1\n")
    return root


@pytest.fixture
def configured(transept_home: Path, data_root: Path) -> settings.Settings:
    jar = transept_home / "fake.jar"
    write_fake_jar(jar)
    chosen = settings.Settings(str(jar), [settings.Repository("Toy", str(data_root))])
    settings.save_settings(chosen)
    return chosen


def write_fake_jar(jar: Path) -> None:
    """Writes a jar that only holds the resources Transept reads: the parameter space of
    the configurable algorithms and their default configurations (copies of the tool's, in
    tests/data)."""
    with zipfile.ZipFile(jar, "w") as archive:
        for space in DATA.glob("MSA*.yaml"):
            archive.write(space, f"parameterSpaces/{space.name}")
        for default in DATA.glob("MSA*Default.txt"):
            archive.write(default, f"defaultConfigurations/{default.name}")


def write_finished_run(runs_root: Path, data_root: Path, run_id: str = "done") -> Path:
    """Writes the files the tool leaves after a successful run of the toy dataset."""
    directory = runner.run_directory(runs_root, "toy", run_id)
    directory.mkdir(parents=True)
    values = [(30.0, 0.50), (25.0, 0.60), (30.0, 0.50), (20.0, 0.55)]
    (directory / "FUN.csv").write_text("".join(f"{a},{b}\n" for a, b in values))
    rows = ALIGNMENTS["mafft"]
    for index in range(len(values)):
        text = "".join(f">p{i + 1}\n{row}\n" for i, row in enumerate(rows))
        (directory / f"MSASol{index}.fasta").write_text(text)
    config = {
        "dataRoot": str(data_root),
        "dataset": "toy",
        "algorithmType": "NSGA_II",
        "maxEvaluations": 200,
        "populationSize": 4,
        "seedMethods": ["mafft", "kalign"],
    }
    (directory / "config.json").write_text(json.dumps(config))
    (directory / "progress.jsonl").write_text(
        '{"evaluations":100,"elapsedMs":500,"best":{"SOPwTP":28.0,"lDDT":0.58}}\n'
        '{"evaluations":200,"elapsedMs":900,"best":{"SOPwTP":30.0,"lDDT":0.60}}\n'
    )
    metadata = {
        "evaluations": 200,
        "runtimeMs": 900,
        "startedAt": "2026-11-04T10:00:00Z",
        "proteinsWithoutStructure": ["p3"],
        "structures": [
            {"protein": "p1", "status": "NUMBERED"},
            {"protein": "p2", "status": "UNVERIFIED"},
            {"protein": "p3", "status": "MISSING_FILES"},
        ],
    }
    (directory / "metadata.json").write_text(json.dumps(metadata))
    return directory


def write_job(runs_root: Path, run_id: str, pid: int | None, log: str = "") -> Path:
    """Writes the files Transept keeps about a job."""
    job = runner.job_directory(runs_root, "toy", run_id)
    job.mkdir(parents=True)
    if pid is not None:
        (job / runner.PID_FILE).write_text(f"{pid}\n")
    (job / runner.LOG_FILE).write_text(log)
    return job


ALIVE_PID = os.getpid()
