"""Alignments compared with a reference alignment, by the `score` command of Transept core.

The reports are kept in `<runs-root>/scores/<dataset>/`, per build of the tool and reference, so
that each one is computed once. No file of a run is touched.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd

from transept import baselines, datasets, runs, settings

TIMEOUT_SECONDS = 600
PAIR_F1 = "Pair F1"
TM_PAIR_F1 = "TM-pair F1"
TM_GAP_RATE = "TM-gap rate"
COVERAGE = "Coverage"
METRICS = (PAIR_F1, TM_PAIR_F1, TM_GAP_RATE, COVERAGE)
RUN_ALIGNMENTS = "MSASol*.fasta"
INTERNAL_SEEDS_DIRECTORY = "seeds"


def has_reference(data_root: Path | str, dataset: str) -> bool:
    """Tells whether a dataset has a reference alignment."""
    return datasets.reference_file(data_root, dataset).is_file()


def command(
    jar: str, data_root: str, dataset: str, root: Path, glob: str, output: Path
) -> list[str]:
    """Returns the command line that compares the alignments of a directory with the reference."""
    return [
        settings.java_command(), "-jar", str(jar), "score",
        "--reference", str(datasets.reference_file(data_root, dataset)),
        "--topology", str(datasets.topology_file(data_root, dataset)),
        "--msa-root", str(root),
        "--glob", glob,
        "--output", str(output),
    ]  # fmt: skip


def _fingerprint(jar: str, data_root: str, dataset: str) -> str:
    reference = datasets.reference_file(data_root, dataset)
    stat = reference.stat()
    description = (
        f"{baselines.jar_fingerprint(jar)}:{reference.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    )
    return hashlib.sha1(description.encode()).hexdigest()[:12]


def _read_report(report: Path) -> pd.DataFrame:
    """Reads a report: `file`, `status`, `message`, and the metrics of the alignments compared."""
    table = pd.read_csv(report, keep_default_na=False, dtype=str)
    # A folder inside the directory holds other copies: only its own alignments count.
    table = table[~table["relative_path"].str.contains("/")].reset_index(drop=True)
    numeric = table[["pair_f1", "tm_pair_f1", "tm_gap_rate", "test_pairs", "reference_pairs"]]
    numeric = numeric.apply(pd.to_numeric, errors="coerce")
    return pd.DataFrame(
        {
            "file": table["msa_file"],
            "status": table["status"],
            "message": table["message"],
            PAIR_F1: numeric["pair_f1"],
            TM_PAIR_F1: numeric["tm_pair_f1"],
            TM_GAP_RATE: numeric["tm_gap_rate"],
            COVERAGE: numeric["test_pairs"] / numeric["reference_pairs"],
        }
    )


def _scores(
    jar: str, data_root: str, dataset: str, runs_root: Path, name: str, root: Path, glob: str
) -> pd.DataFrame | None:
    """Returns a report, computing it the first time; None if the tool could not compare them."""
    fingerprint = _fingerprint(jar, data_root, dataset)
    report = runs_root / "scores" / dataset / f"{name}-{fingerprint}.csv"
    if not report.is_file():
        report.parent.mkdir(parents=True, exist_ok=True)
        partial = report.with_suffix(".partial")
        arguments = command(jar, data_root, dataset, root, glob, partial)
        try:
            subprocess.run(arguments, capture_output=True, timeout=TIMEOUT_SECONDS, check=True)
        except (OSError, subprocess.SubprocessError):
            partial.unlink(missing_ok=True)
            return None
        partial.replace(report)
    return _read_report(report)


def run_scores(jar: str, data_root: str, run: runs.Run, runs_root: Path) -> pd.DataFrame | None:
    """Returns the metrics of the alignments of a run, with their `row` in FUN.csv.

    Returns:
        One row per alignment compared, with `row` and the metrics; None if the tool failed.
    """
    table = _scores(
        jar, data_root, run.dataset, runs_root, f"run-{run.run_id}", run.results, RUN_ALIGNMENTS
    )
    if table is None:
        return None
    compared = table[table["status"] == "ok"].copy()
    compared["row"] = compared["file"].str.extract(r"MSASol(\d+)\.fasta", expand=False).astype(int)
    return compared[["row", *METRICS]].sort_values("row").reset_index(drop=True)


def seed_scores(
    jar: str, data_root: str, run: runs.Run, runs_root: Path, methods: list[str]
) -> pd.DataFrame:
    """Returns the metrics of the seed alignments a run used.

    Args:
        jar: The jar of the tool.
        data_root: The data directory of the run.
        run: The run; its internal seeds are in its results.
        runs_root: The root of the runs.
        methods: The seed methods of the run, as in its configuration.

    Returns:
        One row per seed with `seed`, the metrics and `problem`, which explains why a seed could
        not be compared; empty if the tool failed.
    """
    frames = []
    tools = [method for method in methods if method != "internal"]
    directory = Path(data_root) / "precomputed" / run.dataset
    suffix = f"_{run.dataset}.fasta"
    if tools and directory.is_dir():
        table = _scores(jar, data_root, run.dataset, runs_root, "seeds", directory, f"*{suffix}")
        if table is not None:
            table["seed"] = table["file"].str.removesuffix(suffix)
            frames.append(table[table["seed"].isin(tools)])
    internal = run.results / INTERNAL_SEEDS_DIRECTORY
    if "internal" in methods and internal.is_dir():
        table = _scores(
            jar, data_root, run.dataset, runs_root, f"seeds-{run.run_id}", internal, "*.fasta"
        )
        if table is not None:
            table["seed"] = "internal: " + table["file"].str.removesuffix(".fasta")
            frames.append(table)
    columns = ["seed", *METRICS, "problem"]
    if not frames:
        return pd.DataFrame(columns=columns)
    merged = pd.concat(frames, ignore_index=True)
    merged["problem"] = merged["message"]
    return merged[columns]
