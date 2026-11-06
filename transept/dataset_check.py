"""Whether a dataset can be used, and what it holds: the report behind Explore > Datasets."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from transept import datasets, settings

HELIX = re.compile(f"{datasets.TRANSMEMBRANE}+")
MINIMUM_PROTEINS = 2


class Level(Enum):
    """How a check of a dataset turned out."""

    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Status(Enum):
    """Whether a dataset can be used."""

    READY = "Ready"
    WARNINGS = "Ready, with warnings"
    NOT_USABLE = "Not usable"


@dataclass(slots=True, frozen=True)
class Check:
    """One item of the checklist of a dataset.

    Attributes:
        name: What is checked.
        level: How it turned out.
        message: The explanation for the user.
    """

    name: str
    level: Level
    message: str


@dataclass(slots=True, frozen=True)
class ProteinReport:
    """What a dataset has about a protein.

    Attributes:
        id: Its identifier.
        length: Number of residues.
        helices: Number of transmembrane helices in its topology.
        structure: Whether it has a distance matrix and residue numbers (the lDDT needs them).
        model: Whether it has a structure model (PDB).
    """

    id: str
    length: int
    helices: int
    structure: bool
    model: bool


@dataclass(slots=True, frozen=True)
class SeedReport:
    """A precomputed seed alignment of a dataset.

    Attributes:
        tool: The tool that computed it.
        problem: Why the tool would reject it; None if it is valid.
        known_issue: A known problem of the alignments of this tool, if any.
    """

    tool: str
    problem: str | None
    known_issue: str | None


@dataclass(slots=True, frozen=True)
class DatasetReport:
    """The checklist and the contents of a dataset.

    Attributes:
        name: The name of the dataset.
        checks: The checklist.
        proteins: Its proteins, empty if the topology cannot be read.
        seeds: Its precomputed seed alignments.
        reference: Whether it has a reference alignment.
    """

    name: str
    checks: tuple[Check, ...]
    proteins: tuple[ProteinReport, ...]
    seeds: tuple[SeedReport, ...]
    reference: bool

    @property
    def status(self) -> Status:
        levels = {check.level for check in self.checks}
        if Level.ERROR in levels:
            return Status.NOT_USABLE
        return Status.WARNINGS if Level.WARNING in levels else Status.READY

    @property
    def structures(self) -> int:
        return sum(protein.structure for protein in self.proteins)

    @property
    def valid_seeds(self) -> int:
        return sum(seed.problem is None for seed in self.seeds)

    @property
    def mean_length(self) -> float:
        lengths = [protein.length for protein in self.proteins]
        return sum(lengths) / len(lengths) if lengths else 0.0

    @property
    def max_length(self) -> int:
        return max((protein.length for protein in self.proteins), default=0)


@dataclass(slots=True, frozen=True)
class DatasetEntry:
    """A dataset of a repository, with its report."""

    repository: settings.Repository
    report: DatasetReport

    @property
    def name(self) -> str:
        return self.report.name


def _read_proteins(
    data_root: Path | str, dataset: str
) -> tuple[list[datasets.Protein], str | None]:
    """Returns the proteins of a dataset, or why they cannot be read."""
    try:
        return datasets.read_topology(datasets.topology_file(data_root, dataset)), None
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return [], str(error)


def _topology_check(proteins: list[datasets.Protein], problem: str | None) -> Check:
    name = "Sequences and topology"
    if problem:
        return Check(name, Level.ERROR, f"The topology file cannot be used: {problem}")
    if len(proteins) < MINIMUM_PROTEINS:
        return Check(
            name, Level.ERROR, f"An alignment needs at least {MINIMUM_PROTEINS} proteins; "
            f"this dataset has {len(proteins)}.",
        )  # fmt: skip
    return Check(name, Level.OK, f"{len(proteins)} proteins.")


def _structure_check(proteins: tuple[ProteinReport, ...]) -> Check:
    name = "Structures"
    missing = [protein.id for protein in proteins if not protein.structure]
    if proteins and len(missing) == len(proteins):
        return Check(
            name, Level.ERROR, "No protein has distances (`_D.csv`, `_idx.csv`): without "
            "structures the lDDT is always 0 and the search is not guided by them.",
        )  # fmt: skip
    if missing:
        return Check(
            name, Level.WARNING, f"{len(missing)} of {len(proteins)} proteins have no distances, "
            f"so the lDDT ignores them: {', '.join(missing)}.",
        )  # fmt: skip
    return Check(name, Level.OK, f"Distances of all {len(proteins)} proteins.")


def _model_check(proteins: tuple[ProteinReport, ...]) -> Check:
    name = "Structure models"
    missing = [protein.id for protein in proteins if not protein.model]
    if missing:
        return Check(
            name, Level.INFO, f"No PDB for {len(missing)} of {len(proteins)} proteins: the "
            f"numbering of their residues cannot be checked ({', '.join(missing)}).",
        )  # fmt: skip
    return Check(name, Level.OK, f"PDB files of all {len(proteins)} proteins.")


def _seed_check(seeds: tuple[SeedReport, ...]) -> Check:
    name = "Seed alignments"
    invalid = [seed.tool for seed in seeds if seed.problem]
    valid = len(seeds) - len(invalid)
    available = f"Internal seeds and {valid} precomputed" if valid else "Internal seeds only"
    if invalid:
        return Check(
            name, Level.WARNING, f"{available}; {len(invalid)} cannot be used with this dataset: "
            f"{', '.join(invalid)}.",
        )  # fmt: skip
    return Check(name, Level.OK, f"{available}.")


def _reference_check(reference: bool) -> Check:
    if reference:
        return Check("Reference alignment", Level.OK, "Available.")
    return Check(
        "Reference alignment", Level.INFO,
        "None: alignments cannot be evaluated against a reference, which is usual for new data.",
    )  # fmt: skip


def check_dataset(data_root: Path | str, dataset: str) -> DatasetReport:
    """Checks a dataset and summarises what it holds; it never fails on broken data."""
    proteins, problem = _read_proteins(data_root, dataset)
    missing = set(datasets.proteins_without_structure(data_root, dataset, proteins))
    protein_reports = tuple(
        ProteinReport(
            protein.id,
            len(protein.residues),
            len(HELIX.findall(protein.topology)),
            protein.id not in missing,
            datasets.structure_model_file(data_root, dataset, protein.id).is_file(),
        )
        for protein in proteins
    )
    seeds = tuple(
        SeedReport(
            tool,
            datasets.seed_problem(datasets.seed_file(data_root, dataset, tool), proteins),
            datasets.KNOWN_ISSUES.get(tool),
        )
        for tool in (datasets.list_seed_tools(data_root, dataset) if proteins else [])
    )
    reference = datasets.reference_file(data_root, dataset).is_file()
    checks = [_topology_check(proteins, problem)]
    if protein_reports:
        checks += [
            _structure_check(protein_reports),
            _model_check(protein_reports),
            _seed_check(seeds),
        ]
    checks.append(_reference_check(reference))
    return DatasetReport(dataset, tuple(checks), protein_reports, seeds, reference)


def catalogue(repositories: list[settings.Repository]) -> list[DatasetEntry]:
    """Returns the datasets of the repositories, in that order; a missing repository has none."""
    return [
        DatasetEntry(repository, check_dataset(repository.path, name))
        for repository in repositories
        for name in datasets.list_datasets(repository.path)
    ]
