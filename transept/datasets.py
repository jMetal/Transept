"""What a data directory contains: datasets, seed alignments and topologies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

TOPOLOGY_SUFFIX = "_predicted_topologies.3line"

# The six sequence aligners used as seeds in the benchmark.
DEFAULT_SEED_TOOLS = ("clustalw", "kalign", "mafft", "muscle5", "tcoffee", "tmaligner")

TRANSMEMBRANE = "M"


@dataclass(slots=True, frozen=True)
class Protein:
    """A protein of a dataset, as read from its topology file.

    Attributes:
        id: Identifier: the header text before the first '|'.
        residues: Sequence.
        topology: One letter per residue; 'M' marks transmembrane residues.
    """

    id: str
    residues: str
    topology: str


def topology_file(data_root: Path | str, dataset: str) -> Path:
    """Returns the topology file of a dataset."""
    return Path(data_root) / "sequences" / "tmregions" / f"{dataset}{TOPOLOGY_SUFFIX}"


def list_datasets(data_root: Path | str) -> list[str]:
    """Returns the datasets of a data directory: those with a topology file."""
    directory = Path(data_root) / "sequences" / "tmregions"
    if not directory.is_dir():
        return []
    names = (path.name[: -len(TOPOLOGY_SUFFIX)] for path in directory.glob(f"*{TOPOLOGY_SUFFIX}"))
    return sorted(names)


def list_seed_tools(data_root: Path | str, dataset: str) -> list[str]:
    """Returns the tools with a precomputed alignment: precomputed/<ds>/<tool>_<ds>.fasta."""
    directory = Path(data_root) / "precomputed" / dataset
    suffix = f"_{dataset}.fasta"
    if not directory.is_dir():
        return []
    return sorted(path.name[: -len(suffix)] for path in directory.glob(f"*{suffix}"))


def default_seed_tools(available: list[str]) -> list[str]:
    """Returns the default seeds among the available tools."""
    return [tool for tool in DEFAULT_SEED_TOOLS if tool in available]


def read_topology(path: Path | str) -> list[Protein]:
    """Reads a three-line topology file: header, sequence, topology; blank lines are ignored."""
    lines = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines()]
    lines = [line for line in lines if line]
    if len(lines) % 3 != 0:
        raise ValueError(f"{path} does not have three lines per protein")
    proteins = []
    for index in range(0, len(lines), 3):
        header, residues, topology = lines[index : index + 3]
        if not header.startswith(">"):
            raise ValueError(f"{path}: expected a header at line {index + 1}")
        if len(residues) != len(topology):
            raise ValueError(f"{path}: sequence and topology of {header} differ in length")
        proteins.append(Protein(header[1:].split("|")[0].strip(), residues, topology))
    return proteins


# Seeds whose files are valid but whose alignments are known to be wrong for most classes.
KNOWN_ISSUES = {
    "caretta": "Caretta's alignments are residue-level misaligned in every class except Taste 2 "
    "(recall 0.08-0.17 against GPCRdb in classF and classA_001_19), although its lDDT is high.",
}


def normalize_id(header: str) -> str:
    """Normalises a FASTA header or a protein identifier as Transept core does.

    First word, UniProt accession of `sp|ACC|NAME` or `tr|ACC|NAME` (otherwise the first
    `|`-separated field), without a chain suffix (`:A`) or a `.pdb` extension, lower-cased.
    """
    value = header.strip().removeprefix(">").strip()
    value = value.split()[0] if value.split() else ""
    fields = value.split("|")
    value = fields[1] if len(fields) >= 2 and fields[0].lower() in ("sp", "tr") else fields[0]
    value = value.split(":")[0].strip().lower()
    return value.removesuffix(".pdb").strip()


def seed_file(data_root: Path | str, dataset: str, tool: str) -> Path:
    """Returns the precomputed alignment of a tool."""
    return Path(data_root) / "precomputed" / dataset / f"{tool}_{dataset}.fasta"


def reference_file(data_root: Path | str, dataset: str) -> Path:
    """Returns the reference alignment of a dataset."""
    return Path(data_root) / "reference_alignments" / f"{dataset}.fasta"


def structure_model_file(data_root: Path | str, dataset: str, protein: str) -> Path:
    """Returns the structure model of a protein."""
    return Path(data_root) / "alphafold_pdb" / dataset / f"{protein}.pdb"


def _read_records(path: Path) -> list[tuple[str, str]]:
    records: list[tuple[str, str]] = []
    header, parts = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(parts)))
            header, parts = line, []
        elif line:
            if header is None:
                raise ValueError("sequence data before the first header")
            parts.append(line)
    if header is not None:
        records.append((header, "".join(parts)))
    return records


def _residue_mismatch(protein: Protein, aligned: str) -> str | None:
    ungapped = aligned.replace("-", "")
    expected = protein.residues.upper()
    if ungapped == expected:
        return None
    if len(ungapped) != len(expected):
        return f"the row of '{protein.id}' has {len(ungapped)} residues, expected {len(expected)}"
    position = next(i for i, (a, b) in enumerate(zip(ungapped, expected)) if a != b)
    return (
        f"residue {position + 1} of '{protein.id}' is '{ungapped[position]}' instead of "
        f"'{expected[position]}'"
    )


def seed_problem(path: Path | str, proteins: list[Protein]) -> str | None:
    """Explains why Transept core would reject a seed alignment, or returns None if it is valid.

    Applies the checks of the tool: every protein exactly once, no unexpected proteins, rows of
    the same length, and ungapped rows identical to the sequences of the topology file.
    """
    try:
        records = _read_records(Path(path))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return f"unreadable file ({error})"
    aligned_by_id: dict[str, str] = {}
    for header, sequence in records:
        identifier = normalize_id(header)
        if identifier in aligned_by_id:
            return f"protein '{identifier}' appears twice"
        aligned_by_id[identifier] = sequence.upper().replace(".", "-")
    length = None
    for protein in proteins:
        aligned = aligned_by_id.pop(normalize_id(protein.id), None)
        if aligned is None:
            return f"protein '{protein.id}' is missing"
        if length is not None and len(aligned) != length:
            return f"the row of '{protein.id}' has another aligned length"
        length = len(aligned)
        mismatch = _residue_mismatch(protein, aligned)
        if mismatch:
            return mismatch
    if aligned_by_id:
        return "unexpected proteins: " + ", ".join(sorted(aligned_by_id))
    return None


def proteins_without_structure(
    data_root: Path | str, dataset: str, proteins: list[Protein]
) -> list[str]:
    """Returns the proteins without a distance matrix or residue numbers: the lDDT ignores them."""
    directory = Path(data_root) / "distances" / dataset
    return [
        protein.id
        for protein in proteins
        if not (directory / f"{protein.id}_D.csv").is_file()
        or not (directory / f"{protein.id}_idx.csv").is_file()
    ]
