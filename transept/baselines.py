"""Objective values of the seed alignments, computed by Transept core's `baseline` command."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pandas as pd

from transept import settings

TIMEOUT_SECONDS = 600


def jar_fingerprint(jar: str) -> str:
    """Identifies a build of the tool (path, size and modification time of the jar)."""
    path = Path(jar)
    stat = path.stat() if path.is_file() else None
    description = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}" if stat else str(path)
    return hashlib.sha1(description.encode()).hexdigest()[:12]


def cache_file(
    runs_root: Path, data_root: str, dataset: str, mapping_policy: str, jar: str
) -> Path:
    """Returns where the scores of a dataset computed by a build of the tool are kept.

    The objectives can change between versions of the tool, so the cache depends on the jar; two
    repositories can have datasets with the same name, so it also depends on the data directory.
    """
    description = f"{jar_fingerprint(jar)}:{Path(data_root).resolve()}"
    fingerprint = hashlib.sha1(description.encode()).hexdigest()[:12]
    return runs_root / "baselines" / f"{dataset}-{mapping_policy}-{fingerprint}.csv"


def command(jar: str, data_root: str, dataset: str, mapping_policy: str, output: Path) -> list[str]:
    """Returns the command line that scores the precomputed alignments of a dataset."""
    return [
        settings.java_command(), "-jar", str(jar), "baseline",
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
    cache = cache_file(runs_root, data_root, dataset, mapping_policy, jar)
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


INTERNAL_PREFIX = "internal:"


def internal_seed_files(metadata: dict) -> list[Path]:
    """Returns the files of the internal seeds that a run used, as its metadata.json lists them."""
    return [
        Path(entry["file"])
        for entry in metadata.get("seeds", [])
        if str(entry.get("method", "")).startswith(INTERNAL_PREFIX)
        and entry.get("file")
        and Path(entry["file"]).is_file()
    ]


def internal_cache_file(
    runs_root: Path, data_root: str, dataset: str, mapping_policy: str, jar: str, metadata: dict
) -> Path:
    """Returns where the scores of the internal seeds of a run are kept.

    Besides the build of the tool and the data directory, it depends on the content of the seeds
    (their sha256 in metadata.json), so that runs with the same seeds share it.
    """
    contents = sorted(
        entry.get("sha256", "")
        for entry in metadata.get("seeds", [])
        if str(entry.get("method", "")).startswith(INTERNAL_PREFIX)
    )
    description = f"{jar_fingerprint(jar)}:{Path(data_root).resolve()}:{':'.join(contents)}"
    fingerprint = hashlib.sha1(description.encode()).hexdigest()[:12]
    return runs_root / "baselines" / f"{dataset}-internal-{mapping_policy}-{fingerprint}.csv"


def internal_seed_scores(
    jar: str,
    data_root: str,
    dataset: str,
    metadata: dict,
    runs_root: Path,
    mapping_policy: str = "VERIFIED",
) -> pd.DataFrame:
    """Returns SOPwTP and lDDT of the internal seeds that a run used.

    They are computed by the tool, as the precomputed ones, and cached per build of the tool,
    mapping policy and content of the seeds.

    Returns:
        A table with the columns `method` (`internal:<name>`), `SOPwTP` and `lDDT`; empty if the run
        used no internal seeds or scoring failed.
    """
    empty = pd.DataFrame(columns=["method", "SOPwTP", "lDDT"])
    files = internal_seed_files(metadata)
    if not files:
        return empty
    cache = internal_cache_file(runs_root, data_root, dataset, mapping_policy, jar, metadata)
    if not cache.is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        partial = cache.with_suffix(".partial")
        arguments = [
            *command(jar, data_root, dataset, mapping_policy, partial),
            "--alignments",
            ",".join(str(file) for file in files),
        ]
        try:
            subprocess.run(arguments, capture_output=True, timeout=TIMEOUT_SECONDS, check=True)
        except (OSError, subprocess.SubprocessError):
            return empty
        partial.replace(cache)
    table = pd.read_csv(cache)
    table = table[table["status"] == "ok"]
    table = table.assign(method=INTERNAL_PREFIX + table["method"].astype(str))
    return table[["method", "SOPwTP", "lDDT"]].reset_index(drop=True)
