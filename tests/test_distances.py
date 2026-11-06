"""Distance matrices from structure models, as the benchmark has them."""

from pathlib import Path

import numpy as np
import pytest
from conftest import pdb_text

from transept import distances, settings


def test_should_write_the_distances_and_the_residue_numbers(tmp_path: Path):
    # Arrange
    model = tmp_path / "p1.pdb"
    model.write_text(pdb_text(3))

    # Act
    distances.write_distances(model, tmp_path / "out", "p1")

    # Assert
    matrix = np.loadtxt(tmp_path / "out" / "p1_D.csv", delimiter=",")
    assert matrix.tolist() == [[0, 3, 6], [3, 0, 3], [6, 3, 0]]
    numbers = (tmp_path / "out" / "p1_idx.csv").read_text().split()
    assert numbers == ["1", "2", "3"]


def test_should_cap_the_distances(tmp_path: Path):
    # Arrange: 19 residues, 54 Å from end to end
    model = tmp_path / "p1.pdb"
    model.write_text(pdb_text(19))

    # Act
    distances.write_distances(model, tmp_path, "p1")

    # Assert
    assert np.loadtxt(tmp_path / "p1_D.csv", delimiter=",").max() == distances.MAX_DISTANCE


@pytest.mark.parametrize("text", ["", "not a structure\n"])
def test_should_refuse_a_file_without_structure(tmp_path: Path, text: str):
    model = tmp_path / "p1.pdb"
    model.write_text(text)
    with pytest.raises(distances.StructureError):
        distances.write_distances(model, tmp_path, "p1")


def test_should_reproduce_the_matrices_of_the_example(tmp_path: Path):
    # Arrange: the examples of this repository hold the models and the matrices of the benchmark
    root = settings.REPOSITORY / "examples" / "GPCRdb"
    models = sorted((root / "alphafold_pdb" / "classT2_19").glob("*.pdb"))[:2]
    assert models

    for model in models:
        # Act
        distances.write_distances(model, tmp_path, model.stem)

        # Assert
        expected = root / "distances" / "classT2_19"
        computed = np.loadtxt(tmp_path / f"{model.stem}_D.csv", delimiter=",")
        published = np.loadtxt(expected / f"{model.stem}_D.csv", delimiter=",")
        assert np.abs(computed - published).max() < 0.00011  # four decimals, rounded
        assert (tmp_path / f"{model.stem}_idx.csv").read_text().split() == (
            expected / f"{model.stem}_idx.csv"
        ).read_text().split()
