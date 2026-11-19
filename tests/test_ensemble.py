import numpy as np
import pytest

from transept import ensemble
from transept.alignment import AlignedRow
from transept.datasets import Protein


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


class TestFrontSummary:
    # Two proteins with one helix of 8 residues (MMMMMMMM) between two loop residues.
    PROTEINS = {
        "p1": Protein("p1", "AACDEFGHIKLL", "OOMMMMMMMMOO"),
        "p2": Protein("p2", "AACDEFGHIKLL", "OOMMMMMMMMOO"),
    }

    def test_should_report_full_support_for_helices_aligned_the_same_way(self):
        same = alignment("AACDEFGHIKLL", "AACDEFGHIKLL")
        # The last residue of p1 moves: only the loop changes.
        loops_differ = [
            AlignedRow("p1", "AACDEFGHIKL-L"),
            AlignedRow("p2", "AACDEFGHIKLL-"),
        ]

        found = ensemble.front_summary([same, loops_differ], 0, self.PROTEINS)

        assert found.alignments == 2
        assert found.helices == [(2, 9)]
        assert found.helix_means == [pytest.approx(1.0)]
        assert found.agreement < 1.0

    def test_should_report_a_helix_aligned_in_different_ways(self):
        same = alignment("AACDEFGHIKLL", "AACDEFGHIKLL")
        shifted = [AlignedRow("p1", "AACDEFGHIKLL-"), AlignedRow("p2", "-AACDEFGHIKLL")]

        found = ensemble.front_summary([same, shifted], 0, self.PROTEINS)

        assert found.helix_means[0] < 1.0

    def test_should_find_the_medoid_and_its_support(self):
        common = alignment("AACDEFGHIKLL", "AACDEFGHIKLL")
        shifted = [AlignedRow("p1", "AACDEFGHIKLL-"), AlignedRow("p2", "-AACDEFGHIKLL")]

        found = ensemble.front_summary([shifted, common, common], 0, self.PROTEINS)

        assert found.medoid == 1
        assert set(found.helix_support) == {0, 1}

    def test_should_need_two_alignments(self):
        assert ensemble.front_summary([alignment("AC", "AC")], 0, self.PROTEINS) is None


class TestDescribe:
    PROTEINS = TestFrontSummary.PROTEINS

    def test_should_say_that_the_helices_are_kept_when_they_are(self):
        same = alignment("AACDEFGHIKLL", "AACDEFGHIKLL")
        summary = ensemble.front_summary([same, same], 0, self.PROTEINS)

        text = ensemble.describe(summary)

        assert text.startswith("The 2 alignments of the front share 100.0% of their residue pairs")
        assert "keep the helices of the knee almost unchanged" in text

    def test_should_name_the_helices_that_differ_and_the_subject(self):
        same = alignment("AACDEFGHIKLL", "AACDEFGHIKLL")
        shifted = [AlignedRow("p1", "AACDEFGHIKLL-"), AlignedRow("p2", "-AACDEFGHIKLL")]
        summary = ensemble.front_summary([same, shifted], 0, self.PROTEINS)

        text = ensemble.describe(summary, "the aggregate front")

        assert text.startswith("The 2 alignments of the aggregate front share")
        assert "differ most in TM1" in text
