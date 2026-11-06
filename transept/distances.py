"""Cα distance matrices of structure models, in the format Transept core reads."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from Bio.PDB import PDBParser
from Bio.PDB.PDBExceptions import PDBException

MAX_DISTANCE = 50.0


class StructureError(ValueError):
    """A structure model cannot be read."""


def write_distances(model: Path, directory: Path, protein: str) -> None:
    """Writes `<protein>_D.csv` and `<protein>_idx.csv` from the first chain of a PDB file.

    As in the benchmark: distances in Å with four decimals, capped at 50 Å, and the PDB residue
    number of every row.

    Raises:
        StructureError: If the file cannot be read or has no Cα atoms.
    """
    try:
        structure = PDBParser(QUIET=True).get_structure(protein, model)
        chain = next(structure[0].get_chains())
    except (OSError, ValueError, KeyError, IndexError, StopIteration, PDBException) as error:
        raise StructureError(f"{model.name} cannot be read: {error}") from error
    residues = [residue for residue in chain if residue.id[0] == " " and "CA" in residue]
    if not residues:
        raise StructureError(f"{model.name} has no Cα atoms")
    coordinates = np.array([residue["CA"].get_coord() for residue in residues], dtype=np.float64)
    distances = np.linalg.norm(coordinates[:, None, :] - coordinates[None, :, :], axis=2)
    directory.mkdir(parents=True, exist_ok=True)
    np.savetxt(
        directory / f"{protein}_D.csv",
        np.minimum(distances, MAX_DISTANCE),
        fmt="%.4f",
        delimiter=",",
    )
    np.savetxt(directory / f"{protein}_idx.csv", [residue.id[1] for residue in residues], fmt="%d")
