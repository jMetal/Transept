"""Summaries of an alignment per protein and per helix, and comparison of two alignments.

Alignments are handled as matrices with one row per protein (in the order of the topology file)
and one column per alignment column. The computations are vectorised with NumPy, so that they
remain fast for the largest datasets (about 80 proteins and 2 000 columns).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from transept.alignment import GAP, AlignedRow, helix_breaking_columns, read_fasta
from transept.datasets import TRANSMEMBRANE, Protein, normalize_id


def load_alignment(path: Path | str, proteins: list[Protein]) -> list[AlignedRow]:
    """Reads an alignment and returns its rows in the order of the proteins, with their ids.

    Headers are matched as Transept core does, so seed alignments written by other tools can be
    compared with the solutions of a run.

    Raises:
        ValueError: If a protein is missing.
    """
    by_id = {}
    for row in read_fasta(path):
        by_id[normalize_id(row.id)] = row.aligned.upper().replace(".", GAP)
    rows = []
    for protein in proteins:
        aligned = by_id.get(normalize_id(protein.id))
        if aligned is None:
            raise ValueError(f"protein '{protein.id}' is missing in {path}")
        rows.append(AlignedRow(protein.id, aligned))
    return rows


def residue_index(rows: list[AlignedRow]) -> np.ndarray:
    """Returns an (N, L) matrix with the residue index at every cell, or -1 at gaps."""
    length = max((len(row.aligned) for row in rows), default=0)
    matrix = np.full((len(rows), length), -1, dtype=np.int32)
    for index, row in enumerate(rows):
        residue = np.frombuffer(row.aligned.ljust(length, GAP).encode(), dtype=np.uint8) != ord(GAP)
        matrix[index, residue] = np.arange(int(residue.sum()), dtype=np.int32)
    return matrix


# --- Per protein ---------------------------------------------------------------------------


def identity_matrix(rows: list[AlignedRow]) -> np.ndarray:
    """Returns the percentage identity of every pair of rows over the columns where both have
    residues; the diagonal is 1 and pairs without common columns get NaN."""
    length = max((len(row.aligned) for row in rows), default=0)
    letters = np.array(
        [np.frombuffer(row.aligned.ljust(length, GAP).encode(), dtype=np.uint8) for row in rows]
    ).reshape(len(rows), length)
    present = letters != ord(GAP)
    identity = np.full((len(rows), len(rows)), np.nan)
    for index in range(len(rows)):
        both = present & present[index]
        same = (letters == letters[index]) & both
        counts = both.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            identity[index] = np.where(counts > 0, same.sum(axis=1) / counts, np.nan)
    return identity


def _gap_runs(aligned: str) -> int:
    runs, previous = 0, False
    for char in aligned:
        gap = char == GAP
        runs += gap and not previous
        previous = gap
    return runs


def protein_summary(
    rows: list[AlignedRow], proteins: dict[str, Protein], structure: dict[str, str] | None = None
) -> pd.DataFrame:
    """One row per protein: length, gaps, runs, runs inside helices, identity, structure."""
    identity = identity_matrix(rows)
    np.fill_diagonal(identity, np.nan)
    records = []
    for index, row in enumerate(rows):
        protein = proteins.get(row.id)
        breaking = helix_breaking_columns(row, protein)
        records.append(
            {
                "protein": row.id,
                "length": len(row.aligned) - row.aligned.count(GAP),
                "gaps": row.aligned.count(GAP),
                "gap runs": _gap_runs(row.aligned),
                "gap runs inside helices": _gap_runs(
                    "".join(GAP if c in breaking else "x" for c in range(len(row.aligned)))
                ),
                "mean identity": float(np.nanmean(identity[index])) if len(rows) > 1 else np.nan,
                "structure": (structure or {}).get(row.id, ""),
            }
        )
    return pd.DataFrame(records)


# --- Per helix -----------------------------------------------------------------------------


def _segments(topology: str) -> list[tuple[int, int]]:
    """Maximal runs of transmembrane residues, as (first, last) residue indices."""
    found, start = [], None
    for position, letter in enumerate([*topology, ""]):
        if letter == TRANSMEMBRANE and start is None:
            start = position
        elif letter != TRANSMEMBRANE and start is not None:
            found.append((start, position - 1))
            start = None
    return found


def helix_summary(
    rows: list[AlignedRow],
    proteins: dict[str, Protein],
    helices: list[tuple[int, int]],
    displaced_fraction: float = 0.2,
) -> pd.DataFrame:
    """One row per consensus helix: whether every protein aligns its helix as one block.

    For each protein, the predicted transmembrane segments that reach into the block are checked:
    the helix is *broken* if a gap separates two of its transmembrane residues at a column where
    most proteins have a residue (a deletion with respect to the others), and *displaced* if more
    than `displaced_fraction` of those segments' residues fall outside the block. Columns where
    only a minority of proteins have a residue are *insertion columns*: the gaps they force in the
    other proteins are expected and do not count as breaks.
    """
    index = residue_index(rows)
    occupancy = (index >= 0).mean(axis=0) if index.size else np.zeros(0)
    records = []
    for number, (first, last) in enumerate(helices, start=1):
        block = index[:, first : last + 1]
        majority = {c for c in range(first, last + 1) if occupancy[c] > 0.5}
        broken, displaced, with_helix = [], [], 0
        for row_number, row in enumerate(rows):
            protein = proteins.get(row.id)
            if protein is None:
                continue
            inside = set(int(r) for r in block[row_number] if r >= 0)
            segments = [
                (a, b) for a, b in _segments(protein.topology) if inside & set(range(a, b + 1))
            ]
            if not segments:
                continue
            with_helix += 1
            residues = [r for a, b in segments for r in range(a, b + 1)]
            outside = sum(r not in inside for r in residues)
            if outside > displaced_fraction * len(residues):
                displaced.append(row.id)
            if helix_breaking_columns(row, protein) & majority:
                broken.append(row.id)
        records.append(
            {
                "helix": f"TM{number}",
                "columns": f"{first + 1}-{last + 1}",
                "occupancy": float((block >= 0).mean()) if block.size else 0.0,
                "insertion columns": (last - first + 1) - len(majority),
                "proteins with a helix here": with_helix,
                "intact": with_helix - len(set(broken) | set(displaced)),
                "broken": ", ".join(broken),
                "displaced": ", ".join(displaced),
            }
        )
    return pd.DataFrame(records)


# --- Comparison of two alignments ------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Comparison:
    """Agreement between alignment A and alignment B of the same proteins.

    Attributes:
        pairs_a: Residue pairs aligned in A.
        pairs_b: Residue pairs aligned in B.
        shared: Residue pairs aligned in both.
        column_agreement: For every column of A, the fraction of its pairs also aligned in B
            (NaN for columns with fewer than two residues).
        changed: (row, column) cells of A whose residue keeps less than half of its partners in B.
        protein_agreement: For every protein, the fraction of its pairs in A also aligned in B.
    """

    pairs_a: int
    pairs_b: int
    shared: int
    column_agreement: np.ndarray
    changed: set[tuple[int, int]]
    protein_agreement: np.ndarray

    @property
    def shared_fraction(self) -> float:
        """Shared pairs over the pairs of A."""
        return self.shared / self.pairs_a if self.pairs_a else 0.0


def _pairs_per_column(index: np.ndarray) -> int:
    present = (index >= 0).sum(axis=0)
    return int((present * (present - 1) // 2).sum())


def compare(rows_a: list[AlignedRow], rows_b: list[AlignedRow]) -> Comparison:
    """Compares two alignments of the same proteins, given in the same order."""
    if [row.id for row in rows_a] != [row.id for row in rows_b]:
        raise ValueError("the alignments must contain the same proteins in the same order")
    index_a, index_b = residue_index(rows_a), residue_index(rows_b)
    proteins, length = index_a.shape
    # Column of B of every cell of A (or -1 at gaps).
    column_of_b = np.full_like(index_a, -1)
    for protein in range(proteins):
        residues = index_b[protein] >= 0
        position_in_b = np.full(int(residues.sum()), -1, dtype=np.int32)
        position_in_b[index_b[protein, residues]] = np.nonzero(residues)[0]
        cells = index_a[protein] >= 0
        column_of_b[protein, cells] = position_in_b[index_a[protein, cells]]

    agreement = np.full(length, np.nan)
    changed: set[tuple[int, int]] = set()
    kept = np.zeros(proteins)
    partners = np.zeros(proteins)
    shared = 0
    for column in range(length):
        present = np.nonzero(column_of_b[:, column] >= 0)[0]
        count = len(present)
        if count < 2:
            continue
        targets = column_of_b[present, column]
        values, inverse, sizes = np.unique(targets, return_inverse=True, return_counts=True)
        same = sizes[inverse] - 1  # partners kept by every residue of the column
        shared_here = int((sizes * (sizes - 1) // 2).sum())
        shared += shared_here
        agreement[column] = shared_here / (count * (count - 1) / 2)
        kept[present] += same
        partners[present] += count - 1
        for row in present[same < (count - 1) / 2]:
            changed.add((int(row), column))
    with np.errstate(invalid="ignore", divide="ignore"):
        protein_agreement = np.where(partners > 0, kept / partners, np.nan)
    return Comparison(
        pairs_a=_pairs_per_column(index_a),
        pairs_b=_pairs_per_column(index_b),
        shared=shared,
        column_agreement=agreement,
        changed=changed,
        protein_agreement=protein_agreement,
    )


def helix_agreement(comparison: Comparison, helices: list[tuple[int, int]]) -> list[float]:
    """Mean column agreement inside every helix block (NaN if it has no comparable columns)."""
    values = []
    for first, last in helices:
        block = comparison.column_agreement[first : last + 1]
        values.append(float(np.nanmean(block)) if np.isfinite(block).any() else float("nan"))
    return values
