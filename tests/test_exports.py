import io
import zipfile

from transept import exports
from transept.alignment import AlignedRow
from transept.datasets import Protein

ROWS = [AlignedRow("p1", "AC-DEF"), AlignedRow("p2", "ACGDE-")]
PROTEINS = {"p1": Protein("p1", "ACDEF", "OMMMO"), "p2": Protein("p2", "ACGDE", "OOMMO")}


def test_should_write_fasta():
    assert exports.to_fasta(ROWS) == ">p1\nAC-DEF\n>p2\nACGDE-\n"


def test_should_write_clustal_blocks():
    text = exports.to_clustal(ROWS)
    assert text.startswith("CLUSTAL")
    assert "p1    AC-DEF" in text


def test_should_write_stockholm_with_the_topology_of_every_residue():
    text = exports.to_stockholm(ROWS, PROTEINS)
    lines = text.splitlines()
    assert lines[0] == "# STOCKHOLM 1.0"
    assert lines[-1] == "//"
    assert any(line.startswith("#=GR p1 TM") and line.endswith("OM.MMO") for line in lines)


def test_should_write_jalview_features_of_every_helix():
    text = exports.jalview_features(PROTEINS)
    assert "Transmembrane helix\tp1\t-1\t2\t4\tTransmembrane" in text
    assert "Transmembrane helix\tp2\t-1\t3\t4\tTransmembrane" in text
    assert text.splitlines()[0] == "Transmembrane\tc6dbef"


def test_should_bundle_files_in_a_zip():
    data = exports.bundle({"a.txt": "x", "b.bin": b"y"})
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == ["a.txt", "b.bin"]
        assert archive.read("a.txt") == b"x"


def test_should_keep_only_the_columns_marked():
    rows = [AlignedRow("p1", "AC-D"), AlignedRow("p2", "A-ED")]

    kept = exports.keep_columns(rows, [True, False, False, True])

    assert [row.aligned for row in kept] == ["AD", "AD"]
    assert [row.id for row in kept] == ["p1", "p2"]


def test_should_keep_a_protein_left_with_gaps_only():
    rows = [AlignedRow("p1", "AC"), AlignedRow("p2", "-C")]

    kept = exports.keep_columns(rows, [True, False])

    assert [row.aligned for row in kept] == ["A", "-"]
