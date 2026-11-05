from pathlib import Path

from transept import alignment
from transept.datasets import Protein

PROTEIN = Protein("p1", "ACDEF", "OMMMO")


class TestReading:
    def test_should_read_rows_split_over_several_lines(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "a.fasta"
        path.write_text(">p1 description\nAC-D\nEF\n>p2\nACDEF-\n")

        # Act
        rows = alignment.read_fasta(path)

        # Assert
        assert rows == [alignment.AlignedRow("p1", "AC-DEF"), alignment.AlignedRow("p2", "ACDEF-")]


class TestTopology:
    def test_should_give_the_topology_of_every_column(self):
        # Act
        letters = alignment.topology_row(alignment.AlignedRow("p1", "A-CDEF-"), PROTEIN)

        # Assert
        assert letters == "O-MMMO-"

    def test_should_mark_unknown_residues_without_protein(self):
        assert alignment.topology_row(alignment.AlignedRow("x", "A-C"), None) == "?-?"

    def test_should_count_gap_runs_inside_helices(self):
        # Arrange: one run between C and D (both M), one between A and C (O and M)
        row = alignment.AlignedRow("p1", "A-C--DEF")

        # Act & Assert
        assert alignment.helix_gap_runs(row, PROTEIN) == 1
        assert alignment.helix_gap_runs(row, None) == 0


class TestRendering:
    def test_should_shade_transmembrane_residues_and_escape_identifiers(self):
        # Act
        page = alignment.render_html(
            [alignment.AlignedRow("<p1>", "AC-DEF")], {"<p1>": PROTEIN}, start=0, width=10
        )

        # Assert
        assert page.count('class="tm"') == 3
        assert page.count('class="break"') == 1  # the gap lies between C and D, both M
        assert page.count('class="gap"') == 0
        assert "&lt;p1&gt;" in page
        assert "TM consensus" in page

    def test_should_draw_only_the_requested_columns(self):
        # Act
        page = alignment.render_html(
            [alignment.AlignedRow("p1", "ACDEF")], {"p1": PROTEIN}, start=3, width=2
        )

        # Assert
        assert page.count('class="tm"') == 1  # E is transmembrane, F is not


class TestHelices:
    def test_should_compute_the_transmembrane_fraction_of_every_column(self):
        # Arrange: column 1 has C (M) in p1 and a gap in p2
        proteins = {"p1": PROTEIN, "p2": Protein("p2", "ACDEF", "OOMMO")}
        rows = [alignment.AlignedRow("p1", "ACDEF"), alignment.AlignedRow("p2", "A-CDEF")]

        # Act
        fractions = alignment.consensus(rows, proteins)

        # Assert
        assert fractions[:5] == [0.0, 1.0, 0.5, 1.0, 0.5]

    def test_should_find_the_runs_of_transmembrane_columns(self):
        fractions = [0.0] * 3 + [1.0] * 10 + [0.0] * 4 + [0.9] * 9 + [0.2] * 2 + [1.0] * 3
        assert alignment.helices(fractions, min_length=8) == [(3, 12), (17, 25)]

    def test_should_list_the_columns_of_gaps_that_break_a_helix(self):
        row = alignment.AlignedRow("p1", "A-C--DEF")
        assert alignment.helix_breaking_columns(row, PROTEIN) == {3, 4}
        assert alignment.helix_breaking_columns(row, None) == set()
