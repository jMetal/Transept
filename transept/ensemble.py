"""The alignments of a front taken together, without Streamlit.

A run of Transept ends with a set of alignments that trade the sequence objective against the
structural one. Instead of asking the user to choose among them, the set can be read as a sample
of plausible alignments: where they agree, the alignment does not depend on the trade-off; where
they disagree, it does. This module measures how much they agree, and finds the **medoid**: the
alignment of the set that agrees most with all the others, a consensus that is still one of the
alignments found by the search (so its objectives are known and it keeps the helices whole).

Agreement between two alignments of the same proteins is their pair F1: twice the residue pairs
aligned in both, over the pairs aligned in either. It is symmetric, and 1 only for alignments
that align exactly the same pairs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from transept.alignment import AlignedRow
from transept.analysis import residue_index


def _aligned_pairs(index: np.ndarray) -> int:
    present = (index >= 0).sum(axis=0)
    return int((present * (present - 1) // 2).sum())


def _columns_in(index: np.ndarray, other: np.ndarray) -> np.ndarray:
    """For every cell of an alignment (its residue index matrix), the column of that residue in
    another alignment of the same proteins (its residue index matrix); -1 at gaps."""
    columns = np.full_like(index, -1)
    for protein in range(index.shape[0]):
        residues = other[protein] >= 0
        position = np.full(int(residues.sum()), -1, dtype=np.int32)
        position[other[protein, residues]] = np.nonzero(residues)[0]
        cells = index[protein] >= 0
        columns[protein, cells] = position[index[protein, cells]]
    return columns


def shared_pairs(index: np.ndarray, other: np.ndarray) -> int:
    """The residue pairs aligned in both alignments, given as residue index matrices."""
    columns = _columns_in(index, other)
    cells = columns >= 0
    # Two residues are aligned in both when they share their column in each: count the residues
    # of every (column here, column there) group.
    here = np.broadcast_to(np.arange(index.shape[1]), index.shape)[cells].astype(np.int64)
    key = here * (other.shape[1] + 1) + columns[cells]
    _, sizes = np.unique(key, return_counts=True)
    return int((sizes * (sizes - 1) // 2).sum())


def agreement(rows: list[AlignedRow], other: list[AlignedRow]) -> float:
    """The pair F1 of two alignments of the same proteins, in the same order."""
    return agreement_matrix([rows, other])[0, 1]


def agreement_matrix(alignments: list[list[AlignedRow]]) -> np.ndarray:
    """The agreement (pair F1) between every two alignments of the same proteins, in the same
    order; 1 on the diagonal."""
    indexes = [residue_index(rows) for rows in alignments]
    pairs = [_aligned_pairs(index) for index in indexes]
    count = len(indexes)
    matrix = np.eye(count)
    for first in range(count):
        for second in range(first + 1, count):
            total = pairs[first] + pairs[second]
            shared = shared_pairs(indexes[first], indexes[second])
            matrix[first, second] = matrix[second, first] = 2 * shared / total if total else 1.0
    return matrix


@dataclass(slots=True, frozen=True)
class Consensus:
    """How much a set of alignments agrees, and its most central one.

    Attributes:
        medoid: The position in the set of the alignment with the highest mean agreement with
            the others.
        mean_agreement: For every alignment, its mean agreement with the others.
        overall: The mean agreement between every two alignments of the set.
    """

    medoid: int
    mean_agreement: np.ndarray
    overall: float


def consensus(matrix: np.ndarray) -> Consensus | None:
    """The medoid of a set of alignments, from their agreement matrix; None for an empty set."""
    count = len(matrix)
    if count == 0:
        return None
    if count == 1:
        return Consensus(medoid=0, mean_agreement=np.ones(1), overall=1.0)
    mean = (matrix.sum(axis=1) - 1) / (count - 1)
    overall = float((matrix.sum() - count) / (count * (count - 1)))
    return Consensus(medoid=int(np.argmax(mean)), mean_agreement=mean, overall=overall)
