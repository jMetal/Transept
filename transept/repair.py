"""Repairing an alignment: the gaps that split a transmembrane helix moved out of it.

The `repair` command of Transept core does the work, as `run --repair-seeds` does with the seeds;
this module calls it, counts the gaps inside helices before and after, and compares both alignments
with the reference of the dataset when there is one.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from transept import alignment, analysis, datasets, reference_scores, settings

TIMEOUT_SECONDS = 120
MOVED = re.compile(r": (\d+) gap runs moved")
BEFORE = "before"
AFTER = "after"


class RepairError(RuntimeError):
    """The alignment could not be repaired; the message says why."""


@dataclass(slots=True, frozen=True)
class Repaired:
    """An alignment and its repaired copy.

    Attributes:
        original: The alignment given.
        repaired: The repaired alignment, with the same file name.
        moved_runs: Gap runs moved out of the helices.
    """

    original: Path
    repaired: Path
    moved_runs: int


@lru_cache(maxsize=8)
def supported(jar: str) -> bool:
    """Whether the core jar has the `repair` command (versions before 2026-11-19 do not)."""
    try:
        done = subprocess.run(
            [settings.java_command(), "-jar", jar, "repair", "--help"],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def command(jar: str, topology: Path, alignment_file: Path, output: Path) -> list[str]:
    """The command line that repairs an alignment into a directory."""
    return [
        settings.java_command(), "-jar", str(jar), "repair",
        "--topology", str(topology),
        "--output-dir", str(output),
        str(alignment_file),
    ]  # fmt: skip


def repair(jar: str, topology: Path, alignment_file: Path, output: Path) -> Repaired:
    """Repairs an alignment into `output`, which must not be its directory.

    Raises:
        RepairError: If the tool could not repair it, for instance because its proteins or
            residues are not those of the topology.
    """
    try:
        done = subprocess.run(
            command(jar, topology, alignment_file, output),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise RepairError(f"Transept core could not be started: {error}") from error
    found = MOVED.search(done.stdout)
    if done.returncode != 0 or found is None:
        raise RepairError(_problem(done.stderr) or "Transept core could not repair it.")
    return Repaired(alignment_file, output / alignment_file.name, int(found.group(1)))


def _problem(stderr: str) -> str:
    """The message of the error reported by the tool, without its stack trace."""
    message = re.search(r'"message":"([^"]*)"', stderr)
    if message:
        return message.group(1)
    lines = [line for line in stderr.splitlines() if line.strip() and not line.startswith("\t")]
    return lines[0] if lines else ""


def helix_breaks(repaired: Repaired, proteins: list[datasets.Protein]) -> pd.DataFrame:
    """Gap runs inside helices of every protein, before and after; proteins without any omitted."""
    by_id = {protein.id: protein for protein in proteins}
    before = analysis.load_alignment(repaired.original, proteins)
    after = analysis.load_alignment(repaired.repaired, proteins)
    rows = [
        {
            "protein": old.id,
            BEFORE: alignment.helix_gap_runs(old, by_id.get(old.id)),
            AFTER: alignment.helix_gap_runs(new, by_id.get(new.id)),
        }
        for old, new in zip(before, after, strict=True)
    ]
    table = pd.DataFrame(rows, columns=["protein", BEFORE, AFTER])
    return table[(table[BEFORE] > 0) | (table[AFTER] > 0)].reset_index(drop=True)


def reference_comparison(
    jar: str, data_root: str, dataset: str, repaired: Repaired, scratch: Path
) -> pd.DataFrame | None:
    """The metrics of both alignments against the reference; None if they cannot be computed."""
    if not reference_scores.has_reference(data_root, dataset):
        return None
    rows = []
    for label, path in ((BEFORE, repaired.original), (AFTER, repaired.repaired)):
        folder = scratch / f"score-{label}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / path.name).write_bytes(path.read_bytes())
        report = folder / "report.csv"
        arguments = reference_scores.command(jar, data_root, dataset, folder, "*.fasta", report)
        try:
            subprocess.run(arguments, capture_output=True, timeout=TIMEOUT_SECONDS, check=True)
        except (OSError, subprocess.SubprocessError):
            return None
        table = reference_scores.read_report(report)
        compared = table[table["status"] == "ok"]
        if compared.empty:
            return None
        rows.append({"alignment": label, **compared.iloc[0][list(reference_scores.METRICS)]})
    return pd.DataFrame(rows).set_index("alignment")
