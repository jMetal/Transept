"""What each column and residue of an alignment says to a biologist, without Streamlit.

- **Support**: how robust a column is. Transept returns a set of trade-off alignments, not one; a
  residue is well supported when the other alignments of the set keep it with the same partners.
  It follows the idea of GUIDANCE and of the transitive consistency score of T-Coffee, with the
  set found by the search instead of bootstrap or library alignments.
- **pLDDT**: how confident AlphaFold2 is about the structure of each residue (the B-factor
  column of its models). Where it is low the structural objective says little.
- **Conservation**: how conserved each column is (one minus its normalised Shannon entropy,
  times its occupancy), and the consensus residue.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from transept import superposition
from transept.alignment import GAP, AlignedRow
from transept.analysis import residue_index
from transept.datasets import Protein

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
CONSENSUS_THRESHOLD = 0.5


@dataclass(slots=True, frozen=True)
class Support:
    """How much the other alignments of a set agree with an alignment.

    Attributes:
        column: For every column, the fraction of its residue pairs that the other alignments
            keep, averaged over them; NaN where the column has fewer than two residues.
        residue: For every cell (protein, column), the fraction of its partners in the column
            that stay with it in the other alignments; NaN at gaps.
        alignments: How many other alignments were compared.
    """

    column: np.ndarray
    residue: np.ndarray
    alignments: int


def _columns_in(index: np.ndarray, other: list[AlignedRow]) -> np.ndarray:
    """For every cell of an alignment (its residue index matrix), the column of that residue in
    another alignment of the same proteins; -1 at gaps."""
    index_other = residue_index(other)
    columns = np.full_like(index, -1)
    for protein in range(index.shape[0]):
        residues = index_other[protein] >= 0
        position = np.full(int(residues.sum()), -1, dtype=np.int32)
        position[index_other[protein, residues]] = np.nonzero(residues)[0]
        cells = index[protein] >= 0
        columns[protein, cells] = position[index[protein, cells]]
    return columns


def support(rows: list[AlignedRow], others: list[list[AlignedRow]]) -> Support | None:
    """The support of an alignment by others of the same proteins, in the same order.

    Returns:
        None when there is no other alignment to compare with.
    """
    if not others:
        return None
    index = residue_index(rows)
    present = index >= 0
    count = present.sum(axis=0)
    kept_pairs = np.zeros(index.shape[1])
    kept_partners = np.zeros(index.shape, dtype=float)
    for other in others:
        columns = _columns_in(index, other)
        same = (columns[:, None, :] == columns[None, :, :]) & present[:, None, :] & present[None]
        partners = same.sum(axis=1) - present  # without the residue itself
        kept_partners += np.where(present, partners, 0)
        kept_pairs += partners.sum(axis=0) / 2
    pairs = count * (count - 1) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        column = np.where(count >= 2, kept_pairs / (pairs * len(others)), np.nan)
        residue = np.where(
            present & (count >= 2), kept_partners / ((count - 1) * len(others)), np.nan
        )
    return Support(column=column, residue=residue, alignments=len(others))


def _read_plddt(model: Path) -> tuple[dict[int, float], dict[int, str]]:
    """The pLDDT (B-factor) and the residue of every Cα of a model, by residue number."""
    text = model.read_text(encoding="utf-8")
    plddt: dict[int, float] = {}
    for line in text.splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            number = int(line[22:26])
            try:
                plddt.setdefault(number, float(line[60:66]))
            except ValueError:
                continue
    _, letters = superposition.read_calpha(text)
    return plddt, letters


def plddt(
    rows: list[AlignedRow], proteins: dict[str, Protein], models: dict[str, Path]
) -> np.ndarray:
    """The AlphaFold pLDDT (0-100) of every cell (protein, column); NaN at gaps and where the
    protein has no model or the residue is not in it. Residues are mapped to the model as in the
    3D view: by numbering when it agrees with the sequence, else by a sequence alignment."""
    index = residue_index(rows)
    values = np.full(index.shape, np.nan)
    for number, row in enumerate(rows):
        protein = proteins.get(row.id)
        model = models.get(row.id)
        if protein is None or model is None or not model.is_file():
            continue
        by_residue, letters = _read_plddt(model)
        mapped = superposition.map_residues(protein.residues, letters)
        cells = np.nonzero(index[number] >= 0)[0]
        for column in cells:
            residue_number = mapped.get(int(index[number, column]))
            if residue_number is not None and residue_number in by_residue:
                values[number, column] = by_residue[residue_number]
    return values


@dataclass(slots=True, frozen=True)
class Conservation:
    """How conserved every column is.

    Attributes:
        score: One minus the Shannon entropy of the residues (over the 20 amino acids, natural
            logarithm, normalised to [0, 1]), times the fraction of proteins with a residue.
        consensus: The residue of more than half of the proteins in each column, or "·".
    """

    score: np.ndarray
    consensus: str


def conservation(rows: list[AlignedRow]) -> Conservation:
    length = max((len(row.aligned) for row in rows), default=0)
    score = np.zeros(length)
    consensus = []
    total = len(rows)
    for column in range(length):
        letters = [
            row.aligned[column].upper()
            for row in rows
            if column < len(row.aligned) and row.aligned[column] != GAP
        ]
        standard = [letter for letter in letters if letter in AMINO_ACIDS]
        counts = Counter(standard)
        if standard:
            entropy = -sum(
                (n / len(standard)) * math.log(n / len(standard)) for n in counts.values()
            )
            score[column] = (1 - entropy / math.log(len(AMINO_ACIDS))) * len(letters) / total
        top = counts.most_common(1)
        consensus.append(top[0][0] if top and top[0][1] / total > CONSENSUS_THRESHOLD else "·")
    return Conservation(score=score, consensus="".join(consensus))


def helix_means(values: np.ndarray, helices: list[tuple[int, int]]) -> list[float]:
    """The mean of a per-column value over the columns of every helix, ignoring NaN."""
    means = []
    for first, last in helices:
        block = values[first : last + 1]
        means.append(float(np.nanmean(block)) if np.isfinite(block).any() else float("nan"))
    return means
