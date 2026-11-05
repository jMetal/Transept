import math
from pathlib import Path

import numpy as np
import pytest

from transept import analysis
from transept.alignment import AlignedRow
from transept.datasets import Protein

# Three proteins with one helix (residues C-G, 5 residues) each.
PROTEINS = {
    "p1": Protein("p1", "ACDEFGHI", "OMMMMMOO"),
    "p2": Protein("p2", "ACDEFGHI", "OMMMMMOO"),
    "p3": Protein("p3", "ACDEFGHI", "OMMMMMOO"),
}
ORDER = list(PROTEINS.values())


def rows(*aligned):
    return [AlignedRow(f"p{i + 1}", text) for i, text in enumerate(aligned)]


class TestLoading:
    def test_should_order_and_rename_rows_as_the_topology(self, tmp_path: Path):
        # Arrange: a seed written by another tool, in another order and case
        path = tmp_path / "seed.fasta"
        path.write_text(">P3 x\nacdefghi\n>sp|p1|NAME\nACDEFGHI\n>p2:A\nACDEFGH.I\n")

        # Act
        loaded = analysis.load_alignment(path, ORDER)

        # Assert
        assert [row.id for row in loaded] == ["p1", "p2", "p3"]
        assert loaded[1].aligned == "ACDEFGH-I"

    def test_should_report_a_missing_protein(self, tmp_path: Path):
        path = tmp_path / "seed.fasta"
        path.write_text(">p1\nACDEFGHI\n")
        with pytest.raises(ValueError, match="'p2' is missing"):
            analysis.load_alignment(path, ORDER)


class TestPerProtein:
    def test_should_index_residues_and_mark_gaps(self):
        index = analysis.residue_index(rows("AC-D", "ACD-"))
        assert index.tolist() == [[0, 1, -1, 2], [0, 1, 2, -1]]

    def test_should_compute_identity_over_common_columns(self):
        identity = analysis.identity_matrix(rows("ACDE", "ACDK", "----"))
        assert identity[0, 1] == pytest.approx(0.75)
        assert math.isnan(identity[0, 2])

    def test_should_summarise_gaps_and_identity(self):
        # Arrange: p2 has a gap between E and F, both transmembrane
        summary = analysis.protein_summary(
            rows("ACDEFGHI-", "ACDE-FGHI", "ACDEFGHI-"), PROTEINS, {"p1": "NUMBERED"}
        )

        # Assert
        p2 = summary.set_index("protein").loc["p2"]
        assert (p2["length"], p2["gaps"], p2["gap runs"], p2["gap runs inside helices"]) == (
            8,
            1,
            1,
            1,
        )
        assert summary.set_index("protein").loc["p1", "structure"] == "NUMBERED"


class TestPerHelix:
    def test_should_count_a_gap_where_most_proteins_have_residues_as_a_break(self):
        # Act: p2 has a gap inside the helix block where p1 and p3 have residues
        table = analysis.helix_summary(
            rows("ACDEFGHI-", "ACD-EFGHI", "ACDEFGHI-"), PROTEINS, [(1, 6)]
        )

        # Assert
        assert table.loc[0, "broken"] == "p2"
        assert table.loc[0, "intact"] == 2

    def test_should_not_count_the_gaps_of_an_insertion_column(self):
        # Arrange: p1 has one extra residue in the helix (column 3 holds a residue of p1 only)
        proteins = {**PROTEINS, "p1": Protein("p1", "ACDXEFGHI", "OMMMMMMOO")}
        table = analysis.helix_summary(
            rows("ACDXEFGHI", "ACD-EFGHI", "ACD-EFGHI"), proteins, [(1, 6)]
        )

        # Assert
        assert table.loc[0, "insertion columns"] == 1
        assert table.loc[0, "broken"] == ""
        assert table.loc[0, "intact"] == 3

    def test_should_report_a_displaced_helix(self):
        # Arrange: the helix of p3 is shifted three columns to the right of the block
        table = analysis.helix_summary(
            rows("ACDEFGHI---", "ACDEFGHI---", "A---CDEFGHI"), PROTEINS, [(1, 5)]
        )

        # Assert
        assert table.loc[0, "displaced"] == "p3"


class TestComparison:
    def test_should_count_shared_pairs_and_changed_residues(self):
        # Arrange: B moves the residue D of p2 one column to the right
        a = rows("ACDE", "ACDE", "ACDE")
        b = rows("ACD-E", "AC-DE", "ACD-E")

        # Act
        result = analysis.compare(a, b)

        # Assert: 4 columns x 3 pairs in A; column 2 (D) keeps 1 of its 3 pairs
        assert result.pairs_a == 12
        assert result.pairs_b == 10  # D of p2 is alone in its column of B
        assert result.shared == 10
        assert result.column_agreement.tolist() == pytest.approx([1, 1, 1 / 3, 1])
        assert result.changed == {(1, 2)}
        assert result.protein_agreement[1] == pytest.approx(6 / 8)

    def test_should_be_identical_with_itself(self):
        a = rows("AC-DE", "ACD-E", "ACDE-")
        result = analysis.compare(a, a)
        assert result.shared_fraction == 1.0
        assert result.changed == set()

    def test_should_refuse_different_proteins(self):
        with pytest.raises(ValueError):
            analysis.compare(rows("A", "A"), [AlignedRow("x", "A"), AlignedRow("p2", "A")])

    def test_should_average_the_agreement_inside_every_helix(self):
        result = analysis.compare(rows("ACDE", "ACDE", "ACDE"), rows("ACD-E", "AC-DE", "ACD-E"))
        values = analysis.helix_agreement(result, [(0, 1), (2, 3)])
        assert values == pytest.approx([1.0, (1 / 3 + 1) / 2])
        assert np.isnan(analysis.helix_agreement(result, [(9, 10)])[0])
