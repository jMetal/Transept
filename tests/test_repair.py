"""Repairing an alignment with the `repair` command of Transept core.

The tests that call the tool need a jar with that command (the sibling repository or
TRANSEPT_CORE_JAR) and Java; they are skipped otherwise.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transept import datasets, repair, settings

JAR = settings.default_settings().jar
HAS_REPAIR = (
    Path(JAR).is_file() and settings.java_version() is not None and repair.supported(str(JAR))
)
needs_repair = pytest.mark.skipif(
    not HAS_REPAIR, reason="no Transept core jar with the repair command, or no Java"
)


def topology(data_root: Path) -> Path:
    return datasets.topology_file(data_root, "toy")


def proteins(data_root: Path) -> list[datasets.Protein]:
    return datasets.read_topology(topology(data_root))


class TestProblem:
    def test_should_take_the_message_of_the_error_report(self):
        stderr = '{"type":"InvalidInputFileException","message":"Aligned row of p2 differs"}\n'
        assert repair._problem(stderr) == "Aligned row of p2 differs"

    def test_should_take_the_first_line_without_the_stack_trace(self):
        stderr = "java.lang.IllegalStateException: broken\n\tat org.transept.X\n"
        assert repair._problem(stderr) == "java.lang.IllegalStateException: broken"

    def test_should_say_nothing_when_there_is_nothing(self):
        assert repair._problem("") == ""


class TestHelixBreaks:
    def test_should_count_the_gaps_inside_helices_before_and_after(
        self, data_root: Path, tmp_path: Path
    ):
        # Arrange: kalign splits the helix DEG of p2 between D and E
        repaired_file = tmp_path / "kalign_toy.fasta"
        repaired_file.write_text(">p1\nACDEFGHIK\n>p2\nAC-DEGHIK\n>p3\nA-CEFGHIK\n")
        result = repair.Repaired(
            datasets.seed_file(data_root, "toy", "kalign"), repaired_file, moved_runs=1
        )

        # Act
        table = repair.helix_breaks(result, proteins(data_root))

        # Assert: only p2 had one
        assert table.to_dict("records") == [{"protein": "p2", "before": 1, "after": 0}]


class TestSupported:
    def test_should_say_that_a_jar_without_the_command_does_not_repair(self, tmp_path: Path):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        jar = tmp_path / "empty.jar"
        jar.write_bytes(b"not a jar")

        assert not repair.supported(str(jar))


@needs_repair
class TestRepair:
    def test_should_move_the_gap_out_of_the_helix(self, data_root: Path, tmp_path: Path):
        # Arrange
        original = datasets.seed_file(data_root, "toy", "kalign")

        # Act
        result = repair.repair(str(JAR), topology(data_root), original, tmp_path / "out")

        # Assert: the gap goes before D, the nearest end of the helix
        assert result.moved_runs == 1
        assert result.repaired == tmp_path / "out" / "kalign_toy.fasta"
        rows = result.repaired.read_text().split()
        assert rows[rows.index(">p2") + 1] == "AC-DEGHIK"
        breaks = repair.helix_breaks(result, proteins(data_root))
        assert breaks["after"].sum() == 0

    def test_should_not_move_anything_when_no_helix_is_split(self, data_root: Path, tmp_path: Path):
        original = datasets.seed_file(data_root, "toy", "caretta")

        result = repair.repair(str(JAR), topology(data_root), original, tmp_path / "out")

        assert result.moved_runs == 0

    def test_should_fail_when_the_residues_are_not_those_of_the_proteins(
        self, data_root: Path, tmp_path: Path
    ):
        original = datasets.seed_file(data_root, "toy", "broken")

        with pytest.raises(repair.RepairError, match="p2"):
            repair.repair(str(JAR), topology(data_root), original, tmp_path / "out")

    def test_should_compare_nothing_without_a_reference(self, data_root: Path, tmp_path: Path):
        original = datasets.seed_file(data_root, "toy", "kalign")
        result = repair.repair(str(JAR), topology(data_root), original, tmp_path / "out")

        assert (
            repair.reference_comparison(str(JAR), str(data_root), "toy", result, tmp_path) is None
        )
