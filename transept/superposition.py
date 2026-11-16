"""Proteins superposed according to an alignment, without Streamlit.

An alignment says which residues are equivalent, so it also says how to place the structures of the
proteins on top of each other. If the columns are right, their residues coincide in space.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from Bio.Align import PairwiseAligner
from Bio.Data.PDBData import protein_letters_3to1

from transept import datasets
from transept.alignment import AlignedRow

NUMBERING_AGREEMENT = 0.95
MINIMUM_PAIRS = 3


@dataclass(slots=True, frozen=True)
class Structure:
    """The structure of a protein, related to an alignment.

    Attributes:
        id: The protein.
        pdb: The text of its PDB file.
        coordinates: The position of its Cα atoms, by PDB residue number.
        columns: The PDB residue number of its residue in each column it occupies.
        transmembrane: The columns where its residue is transmembrane.
    """

    id: str
    pdb: str
    coordinates: dict[int, np.ndarray]
    columns: dict[int, int]
    transmembrane: frozenset[int]


@dataclass(slots=True, frozen=True)
class PlacedStructure:
    """A structure moved onto the first one.

    Attributes:
        structure: The structure.
        rotation: The rotation applied to it.
        shift: The translation applied after the rotation.
        pairs: How many residue pairs with the first structure were used; 0 for the first.
        rmsd: The distance between those pairs after moving it, in Å.
    """

    structure: Structure
    rotation: np.ndarray
    shift: np.ndarray
    pairs: int
    rmsd: float

    def position(self, column: int) -> np.ndarray | None:
        """Returns where its residue of a column ends up, if it has one with a structure."""
        number = self.structure.columns.get(column)
        point = None if number is None else self.structure.coordinates.get(number)
        return None if point is None else self.rotation @ point + self.shift

    def moved_pdb(self) -> str:
        """Returns its PDB text with the atoms moved."""
        lines = []
        for line in self.structure.pdb.splitlines():
            if line.startswith("ATOM"):
                point = np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
                x, y, z = self.rotation @ point + self.shift
                lines.append(f"{line[:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}")
            elif line.startswith(("HELIX", "SHEET", "TER", "END")):
                lines.append(line)
        return "\n".join(lines)


def read_calpha(text: str) -> tuple[dict[int, np.ndarray], dict[int, str]]:
    coordinates: dict[int, np.ndarray] = {}
    letters: dict[int, str] = {}
    for line in text.splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            number = int(line[22:26])
            coordinates.setdefault(
                number, np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])])
            )
            letters.setdefault(number, protein_letters_3to1.get(line[17:20].strip(), "X"))
    return coordinates, letters


def map_residues(sequence: str, letters: dict[int, str]) -> dict[int, int]:
    """Returns the PDB number of each index of the sequence: by numbering, or else by alignment."""
    agree = sum(
        1 for number, letter in letters.items()
        if 0 < number <= len(sequence) and sequence[number - 1] == letter
    )  # fmt: skip
    if letters and agree >= NUMBERING_AGREEMENT * len(letters):
        return {number - 1: number for number in letters if 0 < number <= len(sequence)}
    numbers = sorted(letters)
    aligner = PairwiseAligner(
        mode="global", match_score=1, mismatch_score=-1, open_gap_score=-2, extend_gap_score=-0.1
    )
    best = aligner.align(sequence, "".join(letters[number] for number in numbers))[0]
    mapped = {}
    for (first, last), (start, _) in zip(*best.aligned):
        for offset in range(last - first):
            mapped[first + offset] = numbers[start + offset]
    return mapped


def read_structure(row: AlignedRow, protein: datasets.Protein, model: Path) -> Structure:
    """Relates the PDB file of a protein to its row of an alignment."""
    text = model.read_text(encoding="utf-8")
    coordinates, letters = read_calpha(text)
    mapped = map_residues(protein.residues, letters)
    columns = {}
    transmembrane = set()
    index = -1
    for column, symbol in enumerate(row.aligned):
        if symbol != "-":
            index += 1
            if index in mapped:
                columns[column] = mapped[index]
                if protein.topology[index] == datasets.TRANSMEMBRANE:
                    transmembrane.add(column)
    return Structure(protein.id, text, coordinates, columns, frozenset(transmembrane))


def _kabsch(moving: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centre_moving, centre_target = moving.mean(0), target.mean(0)
    u, _, vt = np.linalg.svd((moving - centre_moving).T @ (target - centre_target))
    sign = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1.0, 1.0, sign]) @ u.T
    return rotation, centre_target - rotation @ centre_moving


def superpose(structures: list[Structure]) -> tuple[list[PlacedStructure], list[str]]:
    """Moves the structures onto the first one, using their aligned transmembrane residues.

    Without enough transmembrane pairs, a structure cannot be placed in a meaningful way.

    Returns:
        The structures placed, and the identifiers of those that share too few pairs with the first.
    """
    if not structures:
        return [], []
    first = structures[0]
    placed = [PlacedStructure(first, np.eye(3), np.zeros(3), 0, 0.0)]
    left_out = []
    for item in structures[1:]:
        shared = sorted(item.transmembrane & first.transmembrane)
        if len(shared) < MINIMUM_PAIRS:
            left_out.append(item.id)
            continue
        moving = np.array([item.coordinates[item.columns[c]] for c in shared])
        target = np.array([first.coordinates[first.columns[c]] for c in shared])
        rotation, shift = _kabsch(moving, target)
        distances = moving @ rotation.T + shift - target
        rmsd = float(np.sqrt((distances**2).sum(1).mean()))
        placed.append(PlacedStructure(item, rotation, shift, len(shared), rmsd))
    return placed, left_out


def column_spread(placed: list[PlacedStructure]) -> dict[int, float]:
    """Returns how far the residues of each column are from their centre, in Å.

    Only the columns that are transmembrane in every structure count.
    """
    if not placed:
        return {}
    shared = frozenset.intersection(*[item.structure.transmembrane for item in placed])
    spread = {}
    for column in sorted(shared):
        points = np.array([item.position(column) for item in placed])
        spread[column] = float(np.linalg.norm(points - points.mean(0), axis=1).mean())
    return spread


@dataclass(slots=True, frozen=True)
class ColumnResidue:
    """The residue of one protein in a column, placed in space.

    Attributes:
        protein: The protein.
        residue: Its PDB residue number.
        distance: How far it is from the centre of the residues of the column, in Å.
    """

    protein: str
    residue: int
    distance: float


def column_residues(placed: list[PlacedStructure], column: int) -> list[ColumnResidue]:
    """Returns the residues of a column with a structure, farthest from the centre first."""
    found = [
        (item.structure.id, item.structure.columns[column], point)
        for item in placed
        if (point := item.position(column)) is not None
    ]
    if not found:
        return []
    centre = np.mean([point for _, _, point in found], axis=0)
    residues = [
        ColumnResidue(protein, residue, float(np.linalg.norm(point - centre)))
        for protein, residue, point in found
    ]
    return sorted(residues, key=lambda item: item.distance, reverse=True)
