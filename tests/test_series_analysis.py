"""What independent runs give together."""

from pathlib import Path

import pandas as pd
import pytest
from conftest import ALIGNMENTS

from transept import exports, front, generic_numbers, runs, series_analysis
from transept.series_analysis import FinishedRun


def finished_run(
    seed: int, points: list[tuple[float, float]], root: Path = Path("/r")
) -> FinishedRun:
    values = pd.DataFrame(points, columns=["SOPwTP", "lDDT"])
    return FinishedRun(
        seed, runs.run_of(root, "toy", f"s_seed_{seed}"), values, front.summarize(values)
    )


class TestAggregateFront:
    def test_should_keep_what_no_run_dominates_with_its_seed_and_row(self):
        # Arrange: (1, 0.5) of seed 1 is dominated by (2, 0.6) of seed 2
        first = finished_run(1, [(1.0, 0.5), (3.0, 0.1)])
        second = finished_run(2, [(2.0, 0.6)])

        # Act
        table = series_analysis.aggregate_front([first, second])

        # Assert
        assert table[["seed", "row"]].values.tolist() == [[1, 1], [2, 0]]
        assert table["SOPwTP"].tolist() == [3.0, 2.0]

    def test_should_keep_a_solution_found_twice_once(self):
        table = series_analysis.aggregate_front(
            [finished_run(1, [(1.0, 0.5)]), finished_run(2, [(1.0, 0.5)])]
        )
        assert table["seed"].tolist() == [1]

    def test_should_mark_the_knee_of_the_aggregate_and_the_extremes(self):
        # Arrange: the balanced solution comes from another run than the extremes
        table = series_analysis.aggregate_front(
            [finished_run(1, [(3.0, 0.1), (1.0, 0.6)]), finished_run(2, [(2.5, 0.5)])]
        )

        # Assert
        notes = dict(zip(table["note"], table["seed"]))
        assert notes == {"best SOPwTP": 1, "knee": 2, "best lDDT": 1}

    def test_should_be_empty_without_runs(self):
        assert series_analysis.aggregate_front([]).empty


class TestSummary:
    def test_should_add_the_median_and_the_interquartile_range(self):
        # Arrange
        table = pd.DataFrame({"seed": [1, 2, 3, 4], "best lDDT": [0.1, 0.2, 0.3, 0.4]})

        # Act
        result = series_analysis.with_statistics(table)

        # Assert
        assert result["seed"].tolist() == ["1", "2", "3", "4", "median", "IQR"]
        assert result["best lDDT"].iloc[-2] == pytest.approx(0.25)
        assert result["best lDDT"].iloc[-1] == pytest.approx(0.15)

    def test_should_describe_every_run(self):
        table = series_analysis.run_summary([finished_run(1, [(3.0, 0.1), (1.0, 0.5)])])
        assert table.iloc[0].to_dict() == {
            "seed": 1,
            "non-dominated": 2,
            "best SOPwTP": 3.0,
            "best lDDT": 0.5,
            "runtime (s)": None,
        }

    def test_should_add_the_scores_of_each_run(self):
        summary = pd.DataFrame({"seed": [1, 2]})
        scores = pd.DataFrame({"seed": [1, 1, 2], "row": [0, 1, 0], "Pair F1": [0.5, 0.7, 0.9]})
        result = series_analysis.summary_with_scores(summary, scores)
        assert result["best Pair F1"].tolist() == [0.7, 0.9]
        assert result["median Pair F1"].tolist() == [0.6, 0.9]


class TestExport:
    def test_should_export_the_alignments_of_the_aggregate(self, tmp_path: Path):
        # Arrange
        item = finished_run(1, [(3.0, 0.1)], tmp_path)
        item.run.results.mkdir(parents=True)
        text = "".join(f">p{i + 1}\n{row}\n" for i, row in enumerate(ALIGNMENTS["mafft"]))
        (item.run.results / "MSASol0.fasta").write_text(text)
        aggregate = series_analysis.aggregate_front([item])

        # Act
        files = series_analysis.export_files([item], aggregate, pd.DataFrame({"seed": [1]}), {})

        # Assert
        assert set(files) == {
            "aggregate_front.csv",
            "runs_summary.csv",
            "seed1_MSASol0.fasta",
            "seed1_MSASol0.sto",
        }
        assert exports.bundle(files)


def write_alignments(item: FinishedRun, rows: dict[int, list[str]]) -> None:
    item.run.results.mkdir(parents=True, exist_ok=True)
    for row, aligned in rows.items():
        text = "".join(f">p{i + 1}\n{line}\n" for i, line in enumerate(aligned))
        (item.run.results / f"MSASol{row}.fasta").write_text(text)


class TestAlignmentsOfTheAggregate:
    def test_should_find_the_file_of_every_alignment_in_its_run(self, tmp_path: Path):
        # Arrange
        first = finished_run(1, [(1.0, 0.5), (3.0, 0.1)], tmp_path)
        second = finished_run(2, [(2.0, 0.6)], tmp_path)
        aggregate = series_analysis.aggregate_front([first, second])

        # Act
        paths = series_analysis.alignment_paths([first, second], aggregate)

        # Assert
        assert paths == [
            runs.alignment_file(first.run, 1),
            runs.alignment_file(second.run, 0),
        ]

    def test_should_find_the_knee(self):
        aggregate = series_analysis.aggregate_front(
            [finished_run(1, [(3.0, 0.1), (1.0, 0.6)]), finished_run(2, [(2.5, 0.5)])]
        )
        knee = series_analysis.knee_position(aggregate, ["SOPwTP", "lDDT"])
        assert aggregate.iloc[knee]["seed"] == 2

    def test_should_find_the_knee_of_two_alignments(self):
        # The knee of two is one of the extremes, so its note says "best ..."
        aggregate = series_analysis.aggregate_front([finished_run(1, [(3.0, 0.1), (1.0, 0.6)])])
        assert series_analysis.knee_position(aggregate, ["SOPwTP", "lDDT"]) is not None

    def test_should_summarise_the_agreement_of_the_aggregate(self, tmp_path: Path):
        # Arrange: two runs with different alignments
        first = finished_run(1, [(3.0, 0.1)], tmp_path)
        second = finished_run(2, [(2.0, 0.6)], tmp_path)
        write_alignments(first, {0: ALIGNMENTS["mafft"]})
        write_alignments(second, {0: ALIGNMENTS["kalign"]})
        aggregate = series_analysis.aggregate_front([first, second])
        paths = series_analysis.alignment_paths([first, second], aggregate)

        # Act
        summary = series_analysis.aggregate_summary(paths, 0, {})

        # Assert
        assert summary.alignments == 2
        assert summary.agreement < 1.0

    def test_should_not_measure_the_gpcrdb_consistency_without_the_numbering(
        self, tmp_path: Path, transept_home: Path
    ):
        item = finished_run(1, [(3.0, 0.1)], tmp_path)
        write_alignments(item, {0: ALIGNMENTS["mafft"]})

        found = series_analysis.gpcrdb_consistency([runs.alignment_file(item.run, 0)], {})

        assert found is None
        assert not generic_numbers.cache_directory().exists()


class TestOtherRunsSample:
    @staticmethod
    def runs_with_fronts(count: int, size: int) -> list[FinishedRun]:
        # Non-dominated: one objective goes up as the other goes down
        points = [(float(i), 1.0 - i / size) for i in range(size)]
        return [finished_run(seed, points) for seed in range(1, count + 1)]

    def test_should_take_the_same_number_from_every_other_run(self):
        # Arrange: 4 runs with fronts of 10
        finished = self.runs_with_fronts(4, 10)

        # Act
        paths = series_analysis.other_runs_sample(finished, 2, limit=9)

        # Assert: 3 from each of the other 3 runs, none from seed 2
        seeds = [path.parent.name for path in paths]
        assert len(paths) == 9
        assert sorted(set(seeds)) == ["s_seed_1", "s_seed_3", "s_seed_4"]
        assert all(seeds.count(name) == 3 for name in set(seeds))

    def test_should_take_whole_fronts_when_they_are_small(self):
        finished = self.runs_with_fronts(2, 3)

        paths = series_analysis.other_runs_sample(finished, 1, limit=60)

        assert len(paths) == 3

    def test_should_keep_to_the_limit_with_many_runs(self):
        finished = self.runs_with_fronts(30, 5)

        assert len(series_analysis.other_runs_sample(finished, 1, limit=10)) == 10

    def test_should_be_empty_without_other_runs(self):
        assert series_analysis.other_runs_sample(self.runs_with_fronts(1, 5), 1, 60) == []
