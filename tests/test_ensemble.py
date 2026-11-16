import numpy as np
import pytest

from transept import ensemble
from transept.alignment import AlignedRow


def alignment(*rows: str) -> list[AlignedRow]:
    return [AlignedRow(f"p{number}", row) for number, row in enumerate(rows, start=1)]


class TestAgreement:
    def test_should_be_one_for_the_same_alignment(self):
        rows = alignment("AC-D", "ACED", "-CED")

        assert ensemble.agreement(rows, rows) == pytest.approx(1.0)

    def test_should_be_zero_when_no_pair_is_shared(self):
        first = alignment("AC-", "-AC")
        second = alignment("AC", "AC")

        assert ensemble.agreement(first, second) == pytest.approx(0.0)

    def test_should_be_the_pair_f1(self):
        # First: pairs A-A and C-C (columns 1 and 2). Second: A-A only.
        first = alignment("AC", "AC")
        second = alignment("AC-", "A-C")

        assert ensemble.agreement(first, second) == pytest.approx(2 * 1 / (2 + 1))

    def test_should_be_symmetric(self):
        first = alignment("AC-D", "ACED", "-CED")
        second = alignment("ACD-", "ACED", "C-ED")

        assert ensemble.agreement(first, second) == pytest.approx(ensemble.agreement(second, first))


class TestConsensus:
    def test_should_find_the_alignment_that_agrees_most_with_the_others(self):
        # Two copies of the same alignment and a different one: a copy is the most central.
        common = alignment("ACDE", "ACDE")
        other = alignment("AC-DE", "ACDE-")
        matrix = ensemble.agreement_matrix([other, common, common])

        found = ensemble.consensus(matrix)

        assert found.medoid == 1
        assert found.mean_agreement[1] == pytest.approx(matrix[1, [0, 2]].mean())

    def test_should_average_the_agreement_between_every_two_alignments(self):
        matrix = np.array([[1.0, 0.8, 0.6], [0.8, 1.0, 0.4], [0.6, 0.4, 1.0]])

        assert ensemble.consensus(matrix).overall == pytest.approx(0.6)

    def test_should_handle_a_single_alignment(self):
        found = ensemble.consensus(np.ones((1, 1)))

        assert found.medoid == 0
        assert found.overall == pytest.approx(1.0)

    def test_should_return_none_without_alignments(self):
        assert ensemble.consensus(np.zeros((0, 0))) is None
