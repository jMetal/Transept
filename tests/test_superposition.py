"""Structures superposed according to an alignment."""

from pathlib import Path

import numpy as np
import pytest

from transept import datasets, superposition
from transept.alignment import AlignedRow

SEQUENCE = "ACDEF"
TOPOLOGY = "MMMMM"
LETTERS = {"A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE"}
POINTS = np.array(
    [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 3.0, 0.0], [3.0, 3.0, 3.0], [6.0, 3.0, 3.0]]
)


def pdb(points: np.ndarray, start: int = 1, sequence: str = SEQUENCE) -> str:
    lines = [
        f"ATOM  {i:5d}  CA  {LETTERS[sequence[i]]} A{start + i:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 90.00           C"
        for i, (x, y, z) in enumerate(points)
    ]
    return "\n".join(lines) + "\nEND\n"


def rotate(points: np.ndarray) -> np.ndarray:
    angle = 0.7
    rotation = np.array(
        [[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]]
    )
    return points @ rotation.T + np.array([10.0, -4.0, 2.0])


def structure(
    tmp_path: Path, name: str, points: np.ndarray, aligned: str = SEQUENCE, topology: str = TOPOLOGY
) -> superposition.Structure:
    model = tmp_path / f"{name}.pdb"
    model.write_text(pdb(points))
    return superposition.read_structure(
        AlignedRow(name, aligned), datasets.Protein(name, SEQUENCE, topology), model
    )


class TestReadStructure:
    def test_should_relate_the_columns_to_the_residues(self, tmp_path: Path):
        item = structure(tmp_path, "a", POINTS, "AC--DEF")
        assert item.columns == {0: 1, 1: 2, 4: 3, 5: 4, 6: 5}
        assert item.transmembrane == {0, 1, 4, 5, 6}

    def test_should_mark_only_the_transmembrane_columns(self, tmp_path: Path):
        item = structure(tmp_path, "a", POINTS, topology="OOMMO")
        assert item.transmembrane == {2, 3}

    def test_should_map_by_alignment_when_the_numbering_disagrees(self, tmp_path: Path):
        # Arrange: the model starts at residue 101
        model = tmp_path / "a.pdb"
        model.write_text(pdb(POINTS, start=101))

        # Act
        item = superposition.read_structure(
            AlignedRow("a", SEQUENCE), datasets.Protein("a", SEQUENCE, TOPOLOGY), model
        )

        # Assert
        assert item.columns == {0: 101, 1: 102, 2: 103, 3: 104, 4: 105}


class TestSuperpose:
    def test_should_undo_a_rotation_and_a_translation(self, tmp_path: Path):
        # Act
        placed, left_out = superposition.superpose(
            [structure(tmp_path, "a", POINTS), structure(tmp_path, "b", rotate(POINTS))]
        )

        # Assert
        assert left_out == []
        assert placed[1].rmsd == pytest.approx(0.0, abs=1e-2)  # PDB files have three decimals
        assert placed[1].pairs == 5
        assert placed[1].position(2) == pytest.approx(POINTS[2], abs=1e-2)

    def test_should_not_reflect_a_mirror_image(self, tmp_path: Path):
        # Arrange: chirality must be kept, so a mirror image cannot fit exactly
        mirror = POINTS * np.array([1.0, 1.0, -1.0])

        # Act
        placed, _ = superposition.superpose(
            [structure(tmp_path, "a", POINTS), structure(tmp_path, "b", mirror)]
        )

        # Assert
        assert np.linalg.det(placed[1].rotation) == pytest.approx(1.0)
        assert placed[1].rmsd > 0.1

    def test_should_leave_out_a_protein_with_too_few_pairs(self, tmp_path: Path):
        # Arrange: as in an alignment that separates the helices of two proteins
        first = structure(tmp_path, "a", POINTS, "ACDEF-----")
        second = structure(tmp_path, "b", POINTS, "-----ACDEF")

        # Act
        placed, left_out = superposition.superpose([first, second])

        # Assert
        assert left_out == ["b"]
        assert len(placed) == 1

    def test_should_accept_nothing(self):
        assert superposition.superpose([]) == ([], [])
        assert superposition.column_spread([]) == {}


class TestColumnSpread:
    def test_should_be_zero_when_the_residues_coincide(self, tmp_path: Path):
        placed, _ = superposition.superpose(
            [structure(tmp_path, "a", POINTS), structure(tmp_path, "b", rotate(POINTS))]
        )
        spread = superposition.column_spread(placed)
        assert set(spread) == {0, 1, 2, 3, 4}
        assert max(spread.values()) == pytest.approx(0.0, abs=1e-2)

    def test_should_grow_when_a_column_is_misaligned(self, tmp_path: Path):
        # Arrange: the same irregular structure, shifted one residue in the alignment
        irregular = np.array(
            [[0.0, 0.0, 0.0], [3.0, 1.0, 0.5], [4.0, 4.0, 1.0], [2.0, 6.0, 4.0], [7.0, 5.0, 6.0]]
        )
        placed, _ = superposition.superpose(
            [
                structure(tmp_path, "a", irregular, "ACDEF-"),
                structure(tmp_path, "b", irregular, "-ACDEF"),
            ]
        )

        # Act
        spread = superposition.column_spread(placed)

        # Assert
        assert set(spread) == {1, 2, 3, 4}
        assert max(spread.values()) > 0.1
