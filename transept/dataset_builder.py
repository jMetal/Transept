"""Builds a dataset from the files of the user, without Streamlit.

The files are first laid out in a staging directory and checked with the same report as any other
dataset; only then are they moved to the repository, so a repository never holds half a dataset.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from transept import dataset_check, datasets, distances, internal_seeds

DATASET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
UNSAFE_IN_TOOL_NAME = re.compile(r"[^A-Za-z0-9._-]+")
MODEL_SUFFIX = ".pdb"
MATRIX_SUFFIX = "_D.csv"
NUMBERS_SUFFIX = "_idx.csv"


class DatasetBuildError(ValueError):
    """The files cannot make a dataset; the message says why."""


@dataclass(slots=True, frozen=True)
class Source:
    """A file given by the user: uploaded (`data`) or already on this machine (`path`).

    Attributes:
        name: Its file name.
        data: Its contents, if it was uploaded.
        path: Where it is, otherwise.
    """

    name: str
    data: bytes | None = None
    path: Path | None = None

    def write_to(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.path is not None:
            shutil.copyfile(self.path, target)
        else:
            target.write_bytes(self.data or b"")


@dataclass(slots=True, frozen=True)
class DatasetFiles:
    """What the user gives to build a dataset.

    Attributes:
        name: The name of the dataset.
        topology: Three-line file with the sequences and their topology.
        structures: PDB models, and optionally `<id>_D.csv` and `<id>_idx.csv`.
        seeds: Aligned FASTA files, named after their tool.
        reference: Reference alignment, if there is one.
    """

    name: str
    topology: Source
    structures: tuple[Source, ...] = ()
    seeds: tuple[Source, ...] = ()
    reference: Source | None = None


@dataclass(slots=True, frozen=True)
class StagedDataset:
    """A dataset laid out and checked, not yet in a repository.

    Attributes:
        name: Its name.
        root: The staging directory, with the layout of a repository.
        report: The checklist of the dataset.
        notes: What was done with the files that the checklist does not tell.
    """

    name: str
    root: Path
    report: dataset_check.DatasetReport
    notes: tuple[str, ...]


def structure_sources_in_folder(folder: str) -> tuple[Source, ...]:
    """Returns the structural files of a folder of this machine.

    Raises:
        DatasetBuildError: If the folder does not exist.
    """
    directory = Path(folder).expanduser()
    if not directory.is_dir():
        raise DatasetBuildError(f"The folder {folder} does not exist.")
    suffixes = (MODEL_SUFFIX, MATRIX_SUFFIX, NUMBERS_SUFFIX)
    return tuple(
        Source(path.name, path=path)
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name.endswith(suffixes)
    )


def check_name(name: str, repository: Path | str) -> None:
    """Checks that a dataset of this name can be added to a repository.

    Raises:
        DatasetBuildError: If the name is not valid or is already in use there.
    """
    if not DATASET_NAME.fullmatch(name):
        raise DatasetBuildError(
            "The name of a dataset starts with a letter or a digit, and only has letters, digits, "
            "'.', '_' and '-'."
        )
    if datasets.topology_file(repository, name).exists():
        raise DatasetBuildError(f"My datasets already has a dataset called {name}.")


def _check_identifiers(proteins: list[datasets.Protein]) -> None:
    """The identifiers name files, so they must not reach other directories, and must be unique."""
    seen = set()
    for protein in proteins:
        if not protein.id or protein.id in (".", "..") or "/" in protein.id or "\\" in protein.id:
            raise DatasetBuildError(f"The identifier '{protein.id}' cannot name a file.")
        if protein.id in seen:
            raise DatasetBuildError(f"The protein '{protein.id}' appears twice in the topology.")
        seen.add(protein.id)


def _split_structural_name(name: str) -> tuple[str, str] | None:
    """Returns the protein part and the suffix of the name of a structural file, if it is one."""
    for suffix in (MODEL_SUFFIX, MATRIX_SUFFIX, NUMBERS_SUFFIX):
        if name.endswith(suffix):
            return name[: -len(suffix)], suffix
    return None


def _place_structures(
    sources: tuple[Source, ...], proteins: list[datasets.Protein], root: Path, dataset: str
) -> list[str]:
    """Lays out the structural files, computes the missing distances and returns the notes."""
    identifiers = {datasets.normalize_id(protein.id): protein.id for protein in proteins}
    distance_directory = root / "distances" / dataset
    unmatched = []
    for source in sources:
        name = Path(source.name).name
        parts = _split_structural_name(name)
        protein = identifiers.get(datasets.normalize_id(parts[0])) if parts else None
        if protein is None:
            unmatched.append(name)
        elif parts[1] == MODEL_SUFFIX:
            source.write_to(datasets.structure_model_file(root, dataset, protein))
        else:
            source.write_to(distance_directory / f"{protein}{parts[1]}")
    notes = []
    if unmatched:
        notes.append(
            f"{len(unmatched)} file(s) were not used, because their names do not match any protein "
            f"of the topology (`<id>.pdb`): {', '.join(unmatched)}."
        )
    computed = 0
    for protein in identifiers.values():
        model = datasets.structure_model_file(root, dataset, protein)
        complete = all(
            (distance_directory / f"{protein}{suffix}").is_file()
            for suffix in (MATRIX_SUFFIX, NUMBERS_SUFFIX)
        )
        if complete or not model.is_file():
            continue
        try:
            distances.write_distances(model, distance_directory, protein)
        except distances.StructureError as error:
            model.unlink()
            notes.append(f"The structure of {protein} was not used: {error}.")
        else:
            computed += 1
    if computed:
        notes.append(f"Distances computed from the PDB files of {computed} protein(s).")
    return notes


def _tool_name(source: Source, dataset: str) -> str:
    """The tool of a seed alignment: its file name, without the dataset and the extension."""
    stem = Path(Path(source.name).name).stem.removesuffix(f"_{dataset}")
    tool = UNSAFE_IN_TOOL_NAME.sub("_", stem).strip("._")
    if not tool:
        raise DatasetBuildError(f"The name of {source.name} does not say which tool made it.")
    if tool == internal_seeds.NAME:
        raise DatasetBuildError(
            f"{source.name}: '{tool}' is reserved for the seeds of Transept; rename the file."
        )
    return tool


def stage(files: DatasetFiles, staging: Path, repository: Path | str) -> StagedDataset:
    """Lays out the files of a dataset in a staging directory and checks them.

    A previous attempt with the same name is discarded.

    Args:
        files: The files of the user.
        staging: The directory for the attempts.
        repository: The repository the dataset is meant for.

    Returns:
        The dataset, which may not be usable: its report says why.

    Raises:
        DatasetBuildError: If the files cannot even be laid out.
    """
    check_name(files.name, repository)
    root = staging / files.name
    shutil.rmtree(root, ignore_errors=True)
    topology = datasets.topology_file(root, files.name)
    files.topology.write_to(topology)
    (root / "distances" / files.name).mkdir(parents=True)
    notes: list[str] = []
    try:
        proteins = datasets.read_topology(topology)
    except (OSError, UnicodeDecodeError, ValueError):
        proteins = []  # the report tells what is wrong
    else:
        _check_identifiers(proteins)
    if proteins:
        notes += _place_structures(files.structures, proteins, root, files.name)
        for source in files.seeds:
            tool = _tool_name(source, files.name)
            source.write_to(datasets.seed_file(root, files.name, tool))
        if files.reference is not None:
            files.reference.write_to(datasets.reference_file(root, files.name))
    report = dataset_check.check_dataset(root, files.name)
    return StagedDataset(files.name, root, report, tuple(notes))


def publish(staged: StagedDataset, repository: Path) -> None:
    """Moves a checked dataset to a repository; its files leave the staging directory.

    Raises:
        DatasetBuildError: If the dataset cannot be used, or the name was taken in the meantime.
    """
    if staged.report.status == dataset_check.Status.NOT_USABLE:
        raise DatasetBuildError(f"{staged.name} cannot be used: see its checklist.")
    check_name(staged.name, repository)
    name = staged.name
    for relative in (
        Path("distances") / name,
        Path("alphafold_pdb") / name,
        Path("precomputed") / name,
        Path("reference_alignments") / f"{name}.fasta",
        # Last: the topology is what makes it a dataset of the repository
        Path("sequences") / "tmregions" / f"{name}{datasets.TOPOLOGY_SUFFIX}",
    ):
        source = staged.root / relative
        if source.exists():
            target = repository / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise DatasetBuildError(
                    f"{target} already exists: move it away, or choose another name."
                )
            shutil.move(source, target)
    shutil.rmtree(staged.root, ignore_errors=True)
