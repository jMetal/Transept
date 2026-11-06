"""The figures of independent runs."""

import pandas as pd

from transept import charts


def records(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "evaluations": range(100, 100 * len(values) + 1, 100),
            "seconds": range(len(values)),
            "SOPwTP": values,
            "lDDT": values,
        }
    )


class TestSeriesProgressFigure:
    def test_should_draw_one_panel_per_objective_with_a_line_per_run(self):
        figure = charts.series_progress_figure([records([1, 2]), records([1, 3])], [records([1])])
        assert len(figure.data) == 6
        titles = [annotation.text for annotation in figure.layout.annotations]
        assert titles == ["Best SOPwTP", "Best lDDT"]

    def test_should_draw_the_active_runs_last_and_in_blue(self):
        figure = charts.series_progress_figure([records([1, 2])], [records([1])])
        colours = [trace.line.color for trace in figure.data]
        assert colours == [charts.ALL_COLOUR, charts.FRONT_COLOUR] * 2

    def test_should_ignore_runs_without_records(self):
        empty = pd.DataFrame(columns=["evaluations", "seconds", "SOPwTP", "lDDT"])
        figure = charts.series_progress_figure([empty], [records([1])])
        assert len(figure.data) == 2

    def test_should_draw_nothing_without_records(self):
        assert len(charts.series_progress_figure([], []).data) == 0


class TestSeriesFrontFigure:
    @staticmethod
    def figure():
        table = pd.DataFrame({"SOPwTP": [1.0], "lDDT": [0.5]})
        aggregate = pd.DataFrame(
            {
                "seed": [3, 4],
                "row": [7, 8],
                "SOPwTP": [1.0, 2.0],
                "lDDT": [0.5, 0.4],
                "note": ["knee", ""],
            }
        )
        return charts.series_front_figure([table, table], aggregate)

    def test_should_draw_the_fronts_in_grey_and_the_aggregate_in_blue_on_top(self):
        assert [trace.marker.color for trace in self.figure().data] == [
            charts.ALL_COLOUR,
            charts.ALL_COLOUR,
            charts.FRONT_COLOUR,
            charts.FRONT_COLOUR,
        ]

    def test_should_mark_the_solutions_with_a_note(self):
        marked = self.figure().data[-1]
        assert list(marked.text) == ["knee"]
        assert list(marked.customdata[0]) == [3, 7]
