import json
from pathlib import Path

import pytest
from conftest import ALIVE_PID, write_finished_run, write_job

from transept import runner, runs
from transept.runs import RunState

DEAD_PID = 999_999


def run(root: Path, run_id: str) -> runs.Run:
    return runs.run_of(root, "toy", run_id)


class TestState:
    def test_should_be_finished_when_the_metadata_was_written(self, tmp_path: Path, data_root):
        write_finished_run(tmp_path, data_root)
        assert runs.state(run(tmp_path, "done")) == RunState.FINISHED

    def test_should_be_failed_when_the_tool_wrote_an_error(self, tmp_path: Path):
        # Arrange
        results = runner.run_directory(tmp_path, "toy", "bad")
        results.mkdir(parents=True)
        (results / "error.json").write_text('{"type":"X","message":"wrong seed"}')

        # Act & Assert
        assert runs.state(run(tmp_path, "bad")) == RunState.FAILED
        assert runs.error_message(run(tmp_path, "bad")) == "X: wrong seed"

    def test_should_be_running_while_the_process_lives(self, tmp_path: Path):
        write_job(tmp_path, "live", ALIVE_PID)
        assert runs.state(run(tmp_path, "live")) == RunState.RUNNING

    def test_should_be_cancelled_when_the_studio_marked_it(self, tmp_path: Path):
        # Arrange
        job = write_job(tmp_path, "stop", DEAD_PID)
        (job / runner.CANCELLED_FILE).write_text("")

        # Act & Assert
        assert runs.state(run(tmp_path, "stop")) == RunState.CANCELLED

    def test_should_be_failed_when_the_process_ended_before_starting(self, tmp_path: Path):
        # Arrange: Java could not even start the tool
        write_job(tmp_path, "nojava", DEAD_PID, log="Error: Unable to access jarfile\n")

        # Act & Assert
        assert runs.state(run(tmp_path, "nojava")) == RunState.FAILED
        assert "Unable to access jarfile" in runs.error_message(run(tmp_path, "nojava"))

    def test_should_be_interrupted_when_the_process_is_gone_midway(self, tmp_path: Path):
        # Arrange
        write_job(tmp_path, "gone", DEAD_PID)
        runner.run_directory(tmp_path, "toy", "gone").mkdir(parents=True)

        # Act & Assert
        assert runs.state(run(tmp_path, "gone")) == RunState.INTERRUPTED


class TestListing:
    def test_should_merge_job_and_result_directories(self, tmp_path: Path, data_root):
        # Arrange: one run with results only, one with a job only
        write_finished_run(tmp_path, data_root)
        write_job(tmp_path, "live", ALIVE_PID)

        # Act
        keys = sorted(found.key for found in runs.list_runs(tmp_path))

        # Assert
        assert keys == ["toy / done", "toy / live"]

    def test_should_list_nothing_in_an_empty_directory(self, tmp_path: Path):
        assert runs.list_runs(tmp_path) == []


class TestFiles:
    def test_should_read_progress_values_and_metadata(self, tmp_path: Path, data_root):
        # Arrange
        write_finished_run(tmp_path, data_root)
        done = run(tmp_path, "done")

        # Act
        progress = runs.progress(done)
        values = runs.objective_values(done)

        # Assert
        assert list(progress["evaluations"]) == [100, 200]
        assert progress["seconds"].iloc[-1] == 0.9
        assert list(values.columns) == ["SOPwTP", "lDDT"]
        assert len(values) == 4
        assert runs.metadata(done)["evaluations"] == 200
        assert runs.config(done)["algorithmType"] == "NSGA_II"
        assert runs.alignment_file(done, 2).name == "MSASol2.fasta"

    def test_should_take_the_objectives_from_the_metadata(self, tmp_path: Path, data_root):
        # Arrange
        directory = write_finished_run(tmp_path, data_root)
        done = run(tmp_path, "done")

        # Act & Assert: older runs did not record them and used the default formulation
        assert runs.objective_names(done) == ("SOPwTP", "lDDT")
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["objectives"] = ["SOPwTP", "lDDT", "coverage"]
        (directory / "metadata.json").write_text(json.dumps(metadata))
        assert runs.objective_names(done) == ("SOPwTP", "lDDT", "coverage")
        assert not runs.has_default_objectives(done)

    def test_should_take_the_configuration_from_the_request_before_the_tool_writes_it(
        self, tmp_path: Path
    ):
        # Arrange
        job = write_job(tmp_path, "early", ALIVE_PID)
        request = runner.RunRequest(
            dataset="toy", seeds=("a", "b"), run_id="early", seed=1, max_evaluations=300
        )
        (job / runner.REQUEST_FILE).write_text(
            '{"dataset":"toy","seeds":["a","b"],"run_id":"early","seed":1,"max_evaluations":300}'
        )

        # Act
        config = runs.config(run(tmp_path, "early"))

        # Assert
        assert config["maxEvaluations"] == request.max_evaluations
        assert config["seedMethods"] == ["a", "b"]

    def test_should_return_empty_tables_before_the_tool_writes_anything(self, tmp_path: Path):
        # Arrange
        nothing = run(tmp_path, "nothing")

        # Act & Assert
        assert runs.progress(nothing).empty
        assert runs.objective_values(nothing).empty
        assert runs.metadata(nothing) is None
        assert runs.config(nothing) == {}
        assert runs.error_message(nothing) is None


class TestTrash:
    def test_should_move_a_run_to_the_trash_and_restore_it(self, tmp_path: Path, data_root):
        # Arrange
        write_finished_run(tmp_path, data_root)
        write_job(tmp_path, "done", DEAD_PID)
        done = run(tmp_path, "done")

        # Act
        runs.move_to_trash(tmp_path, done)

        # Assert: gone from the runs, listed in the trash
        assert runs.list_runs(tmp_path) == []
        trashed = runs.list_trash(tmp_path)
        assert [item.key for item in trashed] == ["toy / done"]

        # Act
        restored = runs.restore(tmp_path, trashed[0])

        # Assert
        assert runs.state(restored) == RunState.FINISHED
        assert (restored.job / runner.LOG_FILE).is_file()
        assert runs.list_trash(tmp_path) == []

    def test_should_refuse_to_trash_a_running_run(self, tmp_path: Path):
        write_job(tmp_path, "live", ALIVE_PID)
        with pytest.raises(ValueError, match="still running"):
            runs.move_to_trash(tmp_path, run(tmp_path, "live"))

    def test_should_refuse_to_restore_over_an_existing_run(self, tmp_path: Path, data_root):
        # Arrange: a run is trashed and another one with the same identifier is created
        write_finished_run(tmp_path, data_root)
        runs.move_to_trash(tmp_path, run(tmp_path, "done"))
        write_finished_run(tmp_path, data_root)

        # Act & Assert
        with pytest.raises(FileExistsError):
            runs.restore(tmp_path, runs.list_trash(tmp_path)[0])

    def test_should_empty_the_trash(self, tmp_path: Path, data_root):
        write_finished_run(tmp_path, data_root)
        runs.move_to_trash(tmp_path, run(tmp_path, "done"))
        assert runs.empty_trash(tmp_path) == 1
        assert runs.list_trash(tmp_path) == []
