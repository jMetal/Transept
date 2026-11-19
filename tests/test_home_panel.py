"""What the home page shows besides its links."""

from datetime import datetime
from pathlib import Path

from conftest import write_finished_run, write_job

from transept import home_panel, runs, settings


def test_should_name_the_algorithms_for_people():
    assert home_panel.algorithm_label("NSGA_II") == "NSGA-II"
    assert home_panel.algorithm_label("MOEA_D") == "MOEA/D"
    assert home_panel.algorithm_label("SOMETHING_NEW") == "SOMETHING-NEW"
    assert home_panel.algorithm_label(None) == "Unknown algorithm"


def test_should_name_java_briefly():
    assert home_panel.java_label('openjdk version "21.0.10" 2026-01-20 LTS') == "Java 21"
    assert home_panel.java_label(None) == "Java not found"


def test_should_read_when_a_run_was_launched_from_its_identifier():
    assert home_panel.launched_at("nsga_ii-20261110-120940") == datetime(2026, 11, 10, 12, 9, 40)
    assert home_panel.launched_at("done") is None
    assert home_panel.launched_at("x-20261399-999999") is None


def test_should_summarise_the_runs(configured, data_root: Path):
    # Arrange
    root = settings.runs_root()
    write_finished_run(root, data_root, "first")
    write_finished_run(root, data_root, "second")

    # Act
    summary = home_panel.activity(root, limit=1)

    # Assert
    assert summary.total == 2
    assert summary.finished == 2
    assert summary.running == 0
    assert len(summary.recent) == 1
    assert summary.recent[0].algorithm == "NSGA-II"
    assert summary.recent[0].state == runs.RunState.FINISHED
    assert summary.latest_result is not None
    assert summary.active is None


def test_should_report_the_run_in_progress(configured):
    from conftest import ALIVE_PID as alive

    write_job(settings.runs_root(), "live", alive)
    summary = home_panel.activity(settings.runs_root())
    assert summary.active is not None and summary.active.run_id == "live"
    assert summary.running == 1


def test_should_run_the_example_with_its_precomputed_seeds():
    request = home_panel.example_request(datetime(2026, 11, 16, 10, 0, 0))
    assert request.dataset == "classT2_19"
    assert request.run_id == "example-20261116-100000"
    assert request.algorithm == "NSGA_II"
    assert request.seeds and "internal" not in request.seeds


def test_should_run_the_example_as_a_short_demonstration_with_repaired_seeds():
    from transept import options

    request = home_panel.example_request(datetime(2026, 11, 16, 10, 0, 0))
    assert request.repair_seeds
    assert request.max_evaluations == options.EXAMPLE_MAX_EVALUATIONS
    assert request.max_evaluations < options.DEFAULT_MAX_EVALUATIONS


def test_should_count_what_transept_offers():
    from transept import options

    facts = {fact.label: fact for fact in home_panel.project_facts(17, 2, 3)}
    assert facts["Datasets"].value == "17"
    assert "2 repositories" in facts["Datasets"].detail
    assert facts["Algorithms"].value == str(len(options.ALGORITHMS))
    assert facts["Operators"].value == str(len(options.CROSSOVERS) + len(options.MUTATIONS))
    assert facts["Tutorials"].value == "3"
