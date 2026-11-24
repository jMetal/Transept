"""Whether a run seems to have stopped improving."""

import pandas as pd
import pytest

from transept import convergence


def records(sop: list[float], lddt: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "evaluations": range(100, 100 * len(sop) + 1, 100),
            "seconds": range(len(sop)),
            "SOPwTP": sop,
            "lDDT": lddt,
        }
    )


class TestGenerationsWithoutImprovement:
    def test_should_count_from_the_last_improvement_of_any_objective(self):
        table = records([1, 2, 2, 2, 2], [0.5, 0.5, 0.6, 0.6, 0.6])
        assert convergence.generations_without_improvement(table, 100) == 2

    def test_should_be_zero_while_one_objective_improves(self):
        table = records([1, 1, 1], [0.5, 0.6, 0.7])
        assert convergence.generations_without_improvement(table, 100) == 0

    def test_should_count_from_the_start_when_nothing_improves(self):
        table = records([1, 1, 1, 1], [0.5, 0.5, 0.5, 0.5])
        assert convergence.generations_without_improvement(table, 100) == 3

    @pytest.mark.parametrize(("population", "expected"), [(20, 10), (100, 2), (300, 0)])
    def test_should_measure_generations_with_the_population(self, population, expected):
        table = records([1, 2, 2, 2], [0.5, 0.5, 0.5, 0.5])
        assert convergence.generations_without_improvement(table, population) == expected

    def test_should_not_count_a_fall_and_recovery_as_an_improvement(self):
        table = records([2, 1, 2, 2], [0.5, 0.5, 0.5, 0.5])
        assert convergence.generations_without_improvement(table, 100) == 3

    def test_should_be_zero_without_records(self):
        assert convergence.generations_without_improvement(records([], []), 100) == 0
