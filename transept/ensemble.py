"""The alignments of a front taken together, without Streamlit.

A run of Transept ends with a set of alignments that trade the sequence objective against the
structural one. Instead of asking the user to choose among them, the set can be read as a sample
of plausible alignments: where they agree, the alignment does not depend on the trade-off; where
they disagree, it does. This module measures how much they agree, and finds the **medoid**: the
alignment of the set that agrees most with all the others, a consensus that is still one of the
alignments found by the search (so its objectives are known, and it has no gap inside a helix
that its seed alignments did not already have).

Agreement between two alignments of the same proteins is their pair F1: twice the residue pairs
aligned in both, over the pairs aligned in either. It is symmetric, and 1 only for alignments
that align exactly the same pairs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from transept import alignment, tracks
from transept.alignment import AlignedRow
from transept.analysis import residue_index
from transept.datasets import Protein


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


@dataclass(slots=True, frozen=True)
class FrontSummary:
    """How much the alignments of a front agree, said in a way a biologist can act on.

    Attributes:
        alignments: How many alignments were compared.
        agreement: The mean agreement (pair F1) between every two of them.
        helices: The (first, last) columns of the helices of the reference alignment of the set.
        helix_means: For every helix, the mean support of its columns: the fraction of the
            residue pairs of the reference alignment that the others keep there.
        medoid: The position of the medoid in the set.
        mean_agreement: For every alignment, its mean agreement with the others.
        helix_support: The mean support inside the helices of the reference alignment and of the
            medoid, by their position in the set.
    """

    alignments: int
    agreement: float
    helices: list[tuple[int, int]]
    helix_means: list[float]
    medoid: int
    mean_agreement: np.ndarray
    helix_support: dict[int, float]


def _support_of(
    alignments: list[list[AlignedRow]], position: int, proteins: dict[str, Protein]
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """The support of every column of one alignment of the set by the others, and its helices."""
    chosen = alignments[position]
    others = [rows for number, rows in enumerate(alignments) if number != position]
    return (
        tracks.support(chosen, others).column,
        alignment.helices(alignment.consensus(chosen, proteins)),
    )


def _helix_support(column: np.ndarray, helices: list[tuple[int, int]]) -> float:
    means = tracks.helix_means(column, helices)
    finite = [value for value in means if np.isfinite(value)]
    return float(np.mean(finite)) if finite else float("nan")


def front_summary(
    alignments: list[list[AlignedRow]], reference: int, proteins: dict[str, Protein]
) -> FrontSummary | None:
    """Summarises a front: how much its alignments agree, how much they keep the helices of one of
    them (usually the knee, given by its position), and its medoid.

    Returns:
        None with fewer than two alignments.
    """
    if len(alignments) < 2:
        return None
    found = consensus(agreement_matrix(alignments))
    column, helices = _support_of(alignments, reference, proteins)
    helix_support = {reference: _helix_support(column, helices)}
    if found.medoid != reference:
        helix_support[found.medoid] = _helix_support(
            *_support_of(alignments, found.medoid, proteins)
        )
    return FrontSummary(
        alignments=len(alignments),
        agreement=found.overall,
        helices=helices,
        helix_means=tracks.helix_means(column, helices),
        medoid=found.medoid,
        mean_agreement=found.mean_agreement,
        helix_support=helix_support,
    )


# Below this mean support, a helix is said to differ among the alignments of a front.
WEAK_HELIX = 0.9


def describe(summary: FrontSummary, subject: str = "the front") -> str:
    """The agreement of a front in a sentence or two, for the user.

    Args:
        subject: What the alignments are, e.g. "the aggregate front of 20 runs".
    """
    text = (
        f"The {summary.alignments} alignments of {subject} share "
        f"{summary.agreement:.1%} of their residue pairs on average"
    )
    weak = [
        f"TM{number} ({value:.2f})"
        for number, value in enumerate(summary.helix_means, start=1)
        if value < WEAK_HELIX
    ]
    if not weak:
        return (
            text + ", and keep the helices of the knee almost unchanged (support of 0.9 or more). "
            "You do not have to choose among them: the knee is a balanced default, and the "
            "**Support** track of the alignment shows where they disagree, which is where the "
            "alignment depends on the trade-off between sequence and structure."
        )
    return (
        text + ", and differ most in " + ", ".join(weak) + " (mean support of the helix). Here "
        "the choice matters: compare the knee and the medoid, and use the **Support** track of "
        "the alignment to see which columns depend on the trade-off between sequence and "
        "structure."
    )
