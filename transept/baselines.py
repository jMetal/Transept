"""Objective values of the seed alignments, computed by Transept core's `baseline` command."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd

TIMEOUT_SECONDS = 600


def jar_fingerprint(jar: str) -> str:
    """Identifies a build of the tool (path, size and modification time of the jar)."""
    path = Path(jar)
    stat = path.stat() if path.is_file() else None
    description = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}" if stat else str(path)
    return hashlib.sha1(description.encode()).hexdigest()[:12]


def cache_file(runs_root: Path, dataset: str, mapping_policy: str, jar: str) -> Path:
    """Returns where the scores of a dataset computed by a build of the tool are kept.

    The objectives can change between versions of the tool, so the cache depends on the jar.
    """
    fingerprint = jar_fingerprint(jar)
    return runs_root / "baselines" / f"{dataset}-{mapping_policy}-{fingerprint}.csv"


def command(jar: str, data_root: str, dataset: str, mapping_policy: str, output: Path) -> list[str]:
    """Returns the command line that scores the precomputed alignments of a dataset."""
    return [
        "java", "-jar", str(jar), "baseline",
        "--data-root", str(data_root),
        "--datasets", dataset,
        "--mapping-policy", mapping_policy,
        "--output", str(output),
    ]  # fmt: skip


def seed_scores(
    jar: str,
    data_root: str,
    dataset: str,
    runs_root: Path,
    mapping_policy: str = "VERIFIED",
) -> pd.DataFrame:
    """Returns SOPwTP and lDDT of every valid precomputed alignment of a dataset.

    The objectives must be computed as in the run (same tool and mapping policy), so the tool
    computes them; the result is cached per build of the tool and mapping policy.

    Returns:
        A table with the columns `method`, `SOPwTP` and `lDDT`; empty if scoring failed.
    """
    cache = cache_file(runs_root, dataset, mapping_policy, jar)
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        partial = cache.with_suffix(".partial")
        arguments = command(jar, data_root, dataset, mapping_policy, partial)
        try:
            subprocess.run(arguments, capture_output=True, timeout=TIMEOUT_SECONDS, check=True)
        except (OSError, subprocess.SubprocessError):
            return pd.DataFrame(columns=["method", "SOPwTP", "lDDT"])
        partial.replace(cache)
    table = pd.read_csv(cache)
    table = table[table["status"] == "ok"]
    return table[["method", "SOPwTP", "lDDT"]].reset_index(drop=True)
