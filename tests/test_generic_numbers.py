"""GPCRdb generic residue numbers on an alignment, without the network."""

import json
import urllib.error
from pathlib import Path

import pytest
from conftest import ALIGNMENTS, TOPOLOGY

from transept import datasets, generic_numbers
from transept.alignment import AlignedRow

ROWS = [AlignedRow(f"p{i + 1}", row) for i, row in enumerate(ALIGNMENTS["mafft"])]
# GPCRdb answers made up for the toy proteins: (sequence number, residue, generic number)
ANSWERS = {
    "p1": [(3, "D", "1.49x49"), (4, "E", "1.50x50"), (6, "G", "3.49x49"), (7, "H", "3.50x50"),
           (8, "I", "3.51x51")],
    "p2": [(3, "D", "1.49x49"), (4, "E", "1.50x50"), (5, "G", "3.49x49"), (6, "H", "3.50x50"),
           (7, "I", "3.51x51")],
    "p3": [(2, "C", "1.49x49"), (3, "E", "1.50x50"), (5, "G", "3.49x49"), (6, "H", "3.50x50"),
           (7, "I", "3.51x51")],
}  # fmt: skip


def answer(protein: datasets.Protein, numbered: list[tuple[int, str, str]]) -> list[dict]:
    """A GPCRdb answer: every residue of the sequence, some with a generic number."""
    generic = {number: label for number, _, label in numbered}
    return [
        {
            "sequence_number": number,
            "amino_acid": letter,
            "protein_segment": "TM",
            "display_generic_number": generic.get(number),
        }
        for number, letter in enumerate(protein.residues, start=1)
    ]


@pytest.fixture
def proteins(tmp_path: Path) -> dict[str, datasets.Protein]:
    path = tmp_path / "toy.3line"
    path.write_text(TOPOLOGY)
    return {protein.id: protein for protein in datasets.read_topology(path)}


@pytest.fixture
def cells(transept_home: Path, proteins):
    directory = generic_numbers.cache_directory()
    directory.mkdir(parents=True)
    for name, numbered in ANSWERS.items():
        (directory / f"{name}.json").write_text(json.dumps(answer(proteins[name], numbered)))
    residues = {name: generic_numbers.cached(name) for name in ANSWERS}
    return generic_numbers.cells_by_number(generic_numbers.numbering(ROWS, proteins, residues))


class TestNumbering:
    def test_should_number_every_residue_that_gpcrdb_numbers(self, cells):
        assert cells["1.50x50"] == [(0, 3), (1, 3), (2, 3)]
        assert sorted(cells) == ["1.49x49", "1.50x50", "3.49x49", "3.50x50", "3.51x51"]

    def test_should_find_where_each_number_falls(self, cells):
        reference = generic_numbers.reference_positions(cells, ROWS)
        assert [(item.generic, item.column, item.aligned) for item in reference] == [
            ("1.50x50", 3, 3),
            ("3.50x50", 6, 3),
        ]
        assert reference[0].residues == "EEE"
        shifted = generic_numbers.position(cells, ROWS, "1.49x49")
        assert (shifted.column, shifted.aligned, shifted.receptors) == (2, 2, 3)

    def test_should_measure_the_consistency_of_the_helices(self, cells):
        assert generic_numbers.consistency(cells, ROWS) == (14, 15)
        assert generic_numbers.helix_consistency(cells, ROWS) == {1: 5 / 6, 3: 1.0}

    def test_should_check_the_motifs(self, cells):
        motifs = {row["motif"]: row for row in generic_numbers.motif_rows(cells, ROWS)}
        dry = motifs["D/E-R-Y (3.49–3.51)"]
        assert dry["consensus"] == "GHI"
        assert dry["positions in one column"] == "3 of 3"
        assert dry["columns"] == "6, 7, 8"

    def test_should_mark_the_x50_columns(self, cells):
        assert generic_numbers.x50_line(cells, ROWS, 9) == "···1··3··"


class TestFetch:
    def test_should_use_the_answers_kept_and_survive_without_network(
        self, transept_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: no network
        def offline(*args, **kwargs):
            raise urllib.error.URLError("offline")

        monkeypatch.setattr(generic_numbers.urllib.request, "urlopen", offline)
        directory = generic_numbers.cache_directory()
        directory.mkdir(parents=True)
        (directory / "known_human.json").write_text('[{"sequence_number": 1}]')

        # Act
        found = generic_numbers.fetch_all(["known_human", "other_human"])

        # Assert
        assert found == {"known_human": [{"sequence_number": 1}], "other_human": None}
        assert not (directory / "other_human.json").exists()
