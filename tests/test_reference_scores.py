"""Alignments compared with a reference alignment, without the real tool."""

import sys
from pathlib import Path

import pytest
from conftest import write_finished_run

from transept import datasets, reference_scores, runs, settings

HEADER = (
    "relative_path,run_id,msa_file,sequence_count,pair_precision,pair_recall,pair_f1,"
    "tm_pair_precision,tm_pair_recall,tm_pair_f1,tm_gap_rate,reference_pairs,test_pairs,"
    "correct_pairs,reference_tm_pairs,test_tm_pairs,correct_tm_pairs,tm_gap_count,"
    "tm_gap_opportunities,status,message\n"
)


def row(path: str, f1: float, test_pairs: int = 80, reference_pairs: int = 100) -> str:
    name = path.rsplit("/", 1)[-1]
    return (
        f'"{path}","","{name}",3,0.9,0.8,{f1},0.9,0.8,{f1 + 0.1},0.01,{reference_pairs},'
        f'{test_pairs},70,50,40,35,1,100,ok,""\n'
    )


def failed(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return f'"{path}","","{name}",,,,,,,,,,,,,,,,,failed,"Protein IDs differ"\n'


@pytest.fixture
def report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """Replaces the tool: writes the text of `report["text"]`, and counts its calls."""
    calls = tmp_path / "calls"
    state = {"text": "", "calls": calls}

    def fake(jar, data_root, dataset, root, glob, output):
        script = (
            f"open({str(calls)!r}, 'a').write('x'); open({str(output)!r}, 'w').write("
            f"{state['text']!r})"
        )
        return [sys.executable, "-c", script]

    monkeypatch.setattr(reference_scores, "command", fake)
    return state


@pytest.fixture
def reference(data_root: Path) -> Path:
    path = datasets.reference_file(data_root, "toy")
    path.parent.mkdir(parents=True)
    path.write_text(">p1\nA\n")
    return path


class TestCommand:
    def test_should_build_the_score_command(self, data_root: Path, tmp_path: Path):
        arguments = reference_scores.command(
            "/t.jar", str(data_root), "toy", tmp_path, "MSA*.fasta", tmp_path / "o.csv"
        )
        assert arguments[:4] == [settings.java_command(), "-jar", "/t.jar", "score"]
        assert str(datasets.reference_file(data_root, "toy")) in arguments
        assert arguments[arguments.index("--glob") + 1] == "MSA*.fasta"

    def test_should_tell_whether_there_is_a_reference(self, data_root: Path):
        assert not reference_scores.has_reference(data_root, "toy")
        datasets.reference_file(data_root, "toy").parent.mkdir(parents=True)
        datasets.reference_file(data_root, "toy").write_text(">p1\nA\n")
        assert reference_scores.has_reference(data_root, "toy")


class TestRunScores:
    def test_should_read_the_metrics_of_every_alignment_once(
        self, tmp_path: Path, data_root: Path, reference, report
    ):
        # Arrange
        run = runs.run_of(tmp_path, "toy", "done")
        write_finished_run(tmp_path, data_root)
        report["text"] = HEADER + row("MSASol1.fasta", 0.7) + row("MSASol0.fasta", 0.6, 90)

        # Act
        first = reference_scores.run_scores("/t.jar", str(data_root), run, tmp_path)
        second = reference_scores.run_scores("/t.jar", str(data_root), run, tmp_path)

        # Assert
        assert list(first["row"]) == [0, 1]
        assert first[reference_scores.PAIR_F1].tolist() == [0.6, 0.7]
        assert first[reference_scores.COVERAGE].tolist() == [0.9, 0.8]
        assert first.equals(second)
        assert report["calls"].read_text() == "x"

    def test_should_leave_out_the_alignments_that_could_not_be_compared(
        self, tmp_path: Path, data_root: Path, reference, report
    ):
        run = runs.run_of(tmp_path, "toy", "done")
        write_finished_run(tmp_path, data_root)
        report["text"] = HEADER + row("MSASol0.fasta", 0.6) + failed("MSASol1.fasta")
        table = reference_scores.run_scores("/t.jar", str(data_root), run, tmp_path)
        assert list(table["row"]) == [0]

    def test_should_return_nothing_if_the_tool_fails(
        self, tmp_path: Path, data_root: Path, reference, monkeypatch
    ):
        # Arrange: a jar without the score command, for example
        run = runs.run_of(tmp_path, "toy", "done")
        monkeypatch.setattr(
            reference_scores,
            "command",
            lambda *arguments: [sys.executable, "-c", "raise SystemExit(2)"],
        )

        # Act & Assert
        assert reference_scores.run_scores("/t.jar", str(data_root), run, tmp_path) is None
        assert not list((tmp_path / "scores" / "toy").glob("*.partial"))

    def test_should_compute_again_when_the_reference_changes(
        self, tmp_path: Path, data_root: Path, reference, report
    ):
        # Arrange
        run = runs.run_of(tmp_path, "toy", "done")
        write_finished_run(tmp_path, data_root)
        report["text"] = HEADER + row("MSASol0.fasta", 0.6)
        reference_scores.run_scores("/t.jar", str(data_root), run, tmp_path)

        # Act
        reference.write_text(">p1\nAC\n")
        reference_scores.run_scores("/t.jar", str(data_root), run, tmp_path)

        # Assert
        assert report["calls"].read_text() == "xx"


class TestSeedScores:
    def test_should_keep_only_the_seeds_of_the_run_and_ignore_subfolders(
        self, tmp_path: Path, data_root: Path, reference, report
    ):
        # Arrange
        run = runs.run_of(tmp_path, "toy", "done")
        report["text"] = (
            HEADER
            + row("mafft_toy.fasta", 0.5)
            + row("kalign_toy.fasta", 0.4)
            + row("old/mafft_toy.fasta", 0.1)
            + failed("broken_toy.fasta")
        )

        # Act
        table = reference_scores.seed_scores(
            "/t.jar", str(data_root), run, tmp_path, ["mafft", "broken"]
        )

        # Assert
        assert list(table["seed"]) == ["mafft", "broken"]
        assert table[reference_scores.PAIR_F1].iloc[0] == 0.5
        assert table["problem"].iloc[1] == "Protein IDs differ"

    def test_should_read_the_internal_seeds_of_the_run(
        self, tmp_path: Path, data_root: Path, reference, report
    ):
        # Arrange
        run = runs.run_of(tmp_path, "toy", "done")
        (run.results / "seeds").mkdir(parents=True)
        report["text"] = HEADER + row("biojava-g10x1.fasta", 0.5)

        # Act
        table = reference_scores.seed_scores("/t.jar", str(data_root), run, tmp_path, ["internal"])

        # Assert
        assert list(table["seed"]) == ["internal: biojava-g10x1"]

    def test_should_be_empty_without_seeds_to_compare(
        self, tmp_path: Path, data_root: Path, reference
    ):
        run = runs.run_of(tmp_path, "toy", "done")
        assert reference_scores.seed_scores("/t.jar", str(data_root), run, tmp_path, []).empty
