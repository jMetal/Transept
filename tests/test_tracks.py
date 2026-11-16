"""What each column and residue of an alignment says to a biologist."""

from pathlib import Path

import numpy as np
import pytest

from transept import alignment, tracks
from transept.alignment import AlignedRow
from transept.datasets import Protein

ROWS = [AlignedRow("a", "ACDE-"), AlignedRow("b", "ACDEF"), AlignedRow("c", "AC-DE")]


class TestSupport:
    def test_should_be_full_when_the_others_agree(self):
        found = tracks.support(ROWS, [ROWS, ROWS])
        assert found.alignments == 2
        assert np.nanmin(found.column) == pytest.approx(1.0)
        assert np.isnan(found.residue[0, 4])  # a gap

    def test_should_fall_where_another_alignment_moves_residues(self):
        # Arrange: the other alignment shifts the D and E of c one column to the left
        other = [AlignedRow("a", "ACDE-"), AlignedRow("b", "ACDEF"), AlignedRow("c", "ACDE-")]

        # Act
        found = tracks.support(ROWS, [other])

        # Assert: columns 0-1 agree; in column 3, c's D now pairs with nothing that it paired with
        assert found.column[0] == pytest.approx(1.0)
        assert found.column[3] < 1.0
        assert found.residue[2, 3] < found.residue[0, 0]

    def test_should_need_other_alignments(self):
        assert tracks.support(ROWS, []) is None


class TestPlddt:
    @staticmethod
    def model(path: Path, residues: str, plddt: list[float]) -> Path:
        names = {"A": "ALA", "C": "CYS", "D": "ASP", "E": "GLU", "F": "PHE"}
        lines = [
            f"ATOM  {i:5d}  CA  {names[r]} A{i:4d}    {3.0 * i:8.3f}{0.0:8.3f}{0.0:8.3f}"
            f"  1.00{b:6.2f}           C"
            for i, (r, b) in enumerate(zip(residues, plddt), start=1)
        ]
        path.write_text("\n".join(lines) + "\nEND\n")
        return path

    def test_should_read_the_confidence_of_every_residue(self, tmp_path: Path):
        # Arrange
        proteins = {"a": Protein("a", "ACDE", "OMMO"), "b": Protein("b", "ACDEF", "OMMMO")}
        models = {
            "a": self.model(tmp_path / "a.pdb", "ACDE", [40.0, 95.0, 92.0, 60.0]),
        }
        rows = [AlignedRow("a", "AC-DE"), AlignedRow("b", "ACDEF")]

        # Act
        values = tracks.plddt(rows, proteins, models)

        # Assert: a gap and a protein without a model have no value
        assert values[0, 0] == pytest.approx(40.0)
        assert np.isnan(values[0, 2])
        assert values[0, 4] == pytest.approx(60.0)
        assert np.isnan(values[1]).all()


class TestConservation:
    def test_should_score_and_summarise_every_column(self):
        found = tracks.conservation(ROWS)
        # Column 0 is A in all three proteins; column 4 has F in one and E in another
        assert found.score[0] == pytest.approx(1.0)
        assert found.score[4] < found.score[0]
        assert found.consensus[:2] == "AC"
        assert found.consensus[4] == "·"

    def test_should_average_over_helices_ignoring_missing_values(self):
        values = np.array([1.0, np.nan, 0.5, 0.0])
        assert tracks.helix_means(values, [(0, 2), (3, 3)]) == [0.75, 0.0]


class TestDrawing:
    def test_should_draw_tracks_and_colour_residues(self):
        proteins = {
            "a": Protein("a", "ACDE", "OMMO"),
            "b": Protein("b", "ACDEF", "OMMMO"),
            "c": Protein("c", "ACDE", "OMMO"),
        }
        html = alignment.render_html(
            ROWS,
            proteins,
            0,
            5,
            tracks=[
                alignment.Track("Support", np.array([1.0, 1.0, 0.3, 0.1, np.nan])),
                alignment.Track("pLDDT", np.array([95.0, 80.0, 60.0, 40.0, np.nan]), "plddt"),
            ],
            consensus_line="AC···",
            colour=(np.full((3, 5), 0.6), "fraction"),
        )
        assert "Support" in html and "pLDDT" in html and "Consensus" in html
        for css in ("s3", "s1", "s0", "p3", "p2", "p1", "p0"):
            assert f'class="{css}"' in html
        assert '<span class="s2">A</span>' in html  # residues coloured by their value

    def test_should_shade_on_both_scales(self):
        assert alignment.shade(0.8) == "s3"
        assert alignment.shade(0.1) == "s0"
        assert alignment.shade(91, "plddt") == "p3"
        assert alignment.shade(45, "plddt") == "p0"
        assert alignment.shade(float("nan")) == ""
