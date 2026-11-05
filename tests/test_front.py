import pandas as pd

from transept import front


def values(points):
    return pd.DataFrame(points, columns=[front.FIRST, front.SECOND])


class TestSummarize:
    def test_should_keep_distinct_non_dominated_solutions_best_sopwtp_first(self):
        # Arrange: row 2 repeats row 0, row 3 is dominated by row 1
        table = front.summarize(values([(30, 0.5), (25, 0.6), (30, 0.5), (20, 0.55)]))

        # Assert
        assert list(table["row"]) == [0, 1]
        assert list(table["note"]) == ["best SOPwTP", "best lDDT"]

    def test_should_mark_the_knee_closest_to_the_ideal_point(self):
        # Act
        table = front.summarize(values([(100, 0.0), (90, 0.9), (0, 1.0)]))

        # Assert
        assert table.set_index("row").loc[1, "note"] == "knee"
        assert front.knee_row(table) == 1

    def test_should_handle_a_single_solution(self):
        # Act
        table = front.summarize(values([(10, 0.4)]))

        # Assert
        assert len(table) == 1
        assert front.knee_row(table) == 0

    def test_should_return_an_empty_table_without_solutions(self):
        # Act
        table = front.summarize(values([]))

        # Assert
        assert table.empty
        assert front.knee_row(table) is None


class TestWeightedCompromise:
    def test_should_move_along_the_front_with_the_weight(self):
        # Arrange
        table = front.summarize(values([(100, 0.0), (90, 0.9), (0, 1.0)]))

        # Act & Assert
        assert front.weighted_compromise(table, 1.0) == 0
        assert front.weighted_compromise(table, 0.5) == 1
        assert front.weighted_compromise(table, 0.0) == 2

    def test_should_return_none_without_solutions(self):
        assert front.weighted_compromise(front.summarize(values([])), 0.5) is None


class TestOtherFormulations:
    def test_should_find_the_front_of_three_objectives(self):
        # Arrange: row 3 is dominated by row 0
        table = front.summarize(
            pd.DataFrame(
                [(3.0, 0.1, 0.5), (1.0, 0.9, 0.5), (2.0, 0.5, 0.9), (2.0, 0.1, 0.4)],
                columns=["SOPwTP", "lDDT", "coverage"],
            )
        )

        # Assert
        assert sorted(table["row"]) == [0, 1, 2]
        notes = dict(zip(table["row"], table["note"], strict=True))
        assert notes == {0: "best SOPwTP", 1: "best lDDT", 2: "best coverage"}

    def test_should_rank_the_distinct_values_of_a_single_objective(self):
        # Act
        ranked = front.ranking(pd.DataFrame({"lDDT": [0.5, 0.8, 0.5, 0.8, 0.7]}))

        # Assert
        assert list(ranked["row"]) == [1, 4, 0]
        assert list(ranked["copies"]) == [2, 1, 2]
        assert front.summarize(pd.DataFrame({"lDDT": [0.5, 0.8]}))["row"].tolist() == [1]
