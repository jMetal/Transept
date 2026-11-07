"""The superposed structures as a 3D chart."""

from pathlib import Path

from test_superposition import POINTS, rotate, structure

from transept import structure_chart, superposition


def placed(tmp_path: Path, topology: str = "OMMOM"):
    items, _ = superposition.superpose(
        [
            structure(tmp_path, "a", POINTS, topology=topology),
            structure(tmp_path, "b", rotate(POINTS), topology=topology),
        ]
    )
    return items


class TestFigure:
    def test_should_draw_the_helices_and_the_rest_of_each_protein(self, tmp_path: Path):
        chart = structure_chart.figure(placed(tmp_path), None, True)
        assert [trace.name for trace in chart.data if trace.showlegend is not False] == ["a", "b"]
        assert len(chart.data) == 4

    def test_should_break_the_line_between_helices(self, tmp_path: Path):
        chart = structure_chart.figure(placed(tmp_path), None, False)
        helices = chart.data[0]
        assert list(helices.x).count(None) == 1
        assert len(helices.x) == 4

    def test_should_mark_the_residues_of_a_column(self, tmp_path: Path):
        chart = structure_chart.figure(placed(tmp_path), 2, False)
        marks = chart.data[-1]
        assert marks.name == "column 3"
        assert abs(marks.x[0] - marks.x[1]) < 1e-3
        assert "a residue 3, column 3" in chart.data[0].text
