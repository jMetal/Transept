"""Alignments with their structures superposed, for ChimeraX and PyMOL."""

from pathlib import Path

import numpy as np
from test_superposition import POINTS, SEQUENCE, pdb, rotate

from transept import datasets, structure_export
from transept.alignment import AlignedRow


def package(tmp_path: Path, topology: str = "MMMMM", with_model: tuple[str, ...] = ("a", "b")):
    models = {}
    for name, points in (("a", POINTS), ("b", rotate(POINTS))):
        if name in with_model:
            models[name] = tmp_path / f"{name}.pdb"
            models[name].write_text(pdb(points))
    rows = [AlignedRow(name, SEQUENCE) for name in ("a", "b", "c")]
    proteins = {name: datasets.Protein(name, SEQUENCE, topology) for name in ("a", "b", "c")}
    return structure_export.files(rows, proteins, models, "toy_run_MSASol0")


def coordinates(text: str) -> np.ndarray:
    return np.array(
        [
            [float(line[30:38]), float(line[38:46]), float(line[46:54])]
            for line in text.splitlines()
            if line.startswith("ATOM")
        ]
    )


class TestFiles:
    def test_should_hold_the_structures_the_alignment_and_the_scripts(self, tmp_path: Path):
        files = package(tmp_path)
        assert set(files) == {
            "structures/a.pdb",
            "structures/b.pdb",
            "alignment.fasta",
            "alignment.sto",
            "tm_features.txt",
            "open_in_chimerax.cxc",
            "open_in_pymol.py",
            "README.txt",
        }

    def test_should_move_the_structures_onto_the_reference(self, tmp_path: Path):
        files = package(tmp_path)
        moved = coordinates(files["structures/b.pdb"])
        assert np.allclose(moved, coordinates(files["structures/a.pdb"]), atol=1e-3)
        assert not np.allclose(moved, rotate(POINTS), atol=1e-3)

    def test_should_say_which_proteins_have_no_model(self, tmp_path: Path):
        readme = package(tmp_path)["README.txt"]
        assert "Without a structure model: c." in readme
        assert "reference" in readme

    def test_should_colour_the_transmembrane_residues_in_chimerax(self, tmp_path: Path):
        script = package(tmp_path, topology="OMMOM")["open_in_chimerax.cxc"]
        lines = script.splitlines()
        assert lines[1:4] == [
            "open structures/a.pdb",
            "open structures/b.pdb",
            "open alignment.fasta",
        ]
        assert "color #1:2-3,5 steelblue target c" in lines
        assert "color #2:2-3,5 darkorange target c" in lines

    def test_should_write_a_pymol_script_that_compiles(self, tmp_path: Path):
        script = package(tmp_path, topology="OMMOM")["open_in_pymol.py"]
        compile(script, "open_in_pymol.py", "exec")
        assert "cmd.color('transept_1', 'b and resi 2-3+5')" in script
        assert "os.path.join(here, 'structures', 'b.pdb')" in script


class TestRanges:
    def test_should_group_consecutive_numbers(self):
        assert structure_export._ranges([1, 2, 3, 7, 9, 10]) == [(1, 3), (7, 7), (9, 10)]
        assert structure_export._ranges([]) == []
