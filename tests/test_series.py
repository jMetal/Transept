"""Series of runs: consecutive seeds, launched a few at a time."""

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from transept import runner, runs, series
from transept.runner import RunRequest
from transept.series import SeriesState

REQUEST = RunRequest(dataset="toy", seeds=("internal",), run_id="s", seed=5)


@pytest.fixture
def fake_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replaces the tool: writes metadata.json after the seconds given as the jar, or as soon as a
    STOP file appears, as the tool does."""

    def fake_command(request, jar, data_root, runs_root):
        results = runner.run_directory(runs_root, request.dataset, request.run_id)
        code = (
            "import pathlib, time\n"
            f"directory = pathlib.Path({str(results)!r})\n"
            "directory.mkdir(parents=True)\n"
            "end = time.time() + " + str(jar) + "\n"
            "while time.time() < end and not (directory / 'STOP').exists():\n"
            "    time.sleep(0.02)\n"
            "stopped = 'true' if (directory / 'STOP').exists() else 'false'\n"
            "(directory / 'metadata.json').write_text('{\"stoppedByUser\": ' + stopped + '}')\n"
        )
        return [sys.executable, "-c", code]

    monkeypatch.setattr(runner, "command", fake_command)


def make(tmp_path: Path, count: int = 3, parallel: int = 2, jar: str = "0") -> series.Series:
    """Writes a series without its detached process, so that `drive` can run in the test."""
    directory = series.series_directory(tmp_path, "toy", "s")
    directory.mkdir(parents=True)
    saved = {
        "dataset": "toy",
        "series_id": "s",
        "requests": [
            {**json.loads(json.dumps(_as_dict(member)))}
            for member in series.member_requests(REQUEST, count)
        ],
        "parallel": parallel,
        "jar": jar,
        "data_root": "/data",
        "runs_root": str(tmp_path),
    }
    (directory / series.SERIES_FILE).write_text(json.dumps(saved))
    return series.load(directory)


def _as_dict(request: RunRequest) -> dict:
    return {name: getattr(request, name) for name in RunRequest.__dataclass_fields__}


def states(chosen: series.Series) -> list[str]:
    return [member.state for member in series.members(chosen)]


class TestPlan:
    def test_should_use_consecutive_seeds_and_name_the_runs_after_them(self):
        requests = series.member_requests(REQUEST, 3)
        assert [request.seed for request in requests] == [5, 6, 7]
        assert [request.run_id for request in requests] == ["s_seed_5", "s_seed_6", "s_seed_7"]

    def test_should_refuse_what_cannot_be_run(self):
        assert series.validate(REQUEST, 2, 1) == []
        assert "at least two runs" in series.validate(REQUEST, 1, 1)[0]
        assert "active at a time" in series.validate(REQUEST, 2, 0)[0]
        big = RunRequest(dataset="toy", seeds=("internal",), run_id="s", seed=series.MAX_SEED)
        assert "must not exceed" in series.validate(big, 2, 1)[0]


class TestDrive:
    def test_should_run_everything_and_finish(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = make(tmp_path)

        # Act
        series.drive(chosen, poll_seconds=0.05)
        for member in series.members(chosen):
            wait_until_it_ends(member.run)

        # Assert
        assert states(chosen) == ["finished"] * 3
        assert series.state(chosen) == SeriesState.FINISHED

    def test_should_keep_at_most_the_runs_allowed_active(self, tmp_path, fake_tool, monkeypatch):
        # Arrange: count the active runs at every launch
        chosen = make(tmp_path, count=4, parallel=2, jar="0.2")
        launch = runner.launch
        peak = []

        def counting(request, jar, data_root, runs_root):
            active = [
                member
                for member in series.members(chosen)
                if member.state == runs.RunState.RUNNING.value
            ]
            peak.append(len(active))
            return launch(request, jar, data_root, runs_root)

        monkeypatch.setattr(runner, "launch", counting)

        # Act
        series.drive(chosen, poll_seconds=0.02)

        # Assert
        assert len(peak) == 4
        assert max(peak) < 2

    def test_should_stop_launching_when_cancelled(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = make(tmp_path, count=3, parallel=1, jar="30")
        (chosen.directory / series.CANCELLED_FILE).touch()

        # Act
        series.drive(chosen, poll_seconds=0.02)

        # Assert
        assert states(chosen) == [series.NOT_STARTED] * 3
        assert series.state(chosen) == SeriesState.CANCELLED


def test_should_go_on_when_an_identifier_was_taken(tmp_path: Path, fake_tool):
    # Arrange
    chosen = make(tmp_path, count=2, parallel=1)
    runner.job_directory(tmp_path, "toy", "s_seed_5").mkdir(parents=True)

    # Act
    series.drive(chosen, poll_seconds=0.02)

    # Assert
    wait_until_it_ends(series.members(chosen)[1].run)
    assert states(chosen)[1] == "finished"


def wait_until_it_ends(run: runs.Run) -> None:
    for _ in range(100):
        if runs.state(run) != runs.RunState.RUNNING:
            return
        time.sleep(0.05)


class TestLaunch:
    def test_should_refuse_an_identifier_in_use(self, tmp_path: Path):
        # Arrange
        make(tmp_path)

        # Act & Assert
        with pytest.raises(FileExistsError, match="Series 's' already exists"):
            series.launch(REQUEST, 3, 1, "/t.jar", "/data", tmp_path)

    def test_should_refuse_a_run_in_use(self, tmp_path: Path):
        # Arrange
        runner.job_directory(tmp_path, "toy", "s_seed_6").mkdir(parents=True)

        # Act & Assert
        with pytest.raises(FileExistsError, match="Run 's_seed_6' already exists"):
            series.launch(REQUEST, 3, 1, "/t.jar", "/data", tmp_path)
        assert not series.series_directory(tmp_path, "toy", "s").exists()

    def test_should_survive_as_a_process_of_its_own(self, tmp_path: Path):
        # Act: the real process; the jar does not exist, so its runs fail at once
        chosen = series.launch(REQUEST, 2, 1, "/no.jar", "/data", tmp_path)

        # Assert
        assert runner.read_pid(chosen.directory) is not None
        for _ in range(200):
            if series.state(chosen) != SeriesState.RUNNING:
                break
            time.sleep(0.05)
        assert series.state(chosen) == SeriesState.FINISHED_WITH_PROBLEMS
        assert states(chosen) == [runs.RunState.FAILED.value] * 2
        assert (chosen.directory / series.LOG_FILE).read_text() == ""


class TestStates:
    def test_should_say_it_stopped_when_its_process_is_gone(self, tmp_path: Path):
        chosen = make(tmp_path)
        (chosen.directory / runner.PID_FILE).write_text("999999\n")
        assert states(chosen) == [series.NOT_STARTED] * 3
        assert series.state(chosen) == SeriesState.STOPPED

    def test_should_queue_while_its_process_is_alive(self, tmp_path: Path):
        chosen = make(tmp_path)
        (chosen.directory / runner.PID_FILE).write_text(f"{os.getpid()}\n")
        assert states(chosen) == [series.QUEUED] * 3
        assert series.state(chosen) == SeriesState.RUNNING

    def test_should_cancel_the_active_runs(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = make(tmp_path, count=2, parallel=2, jar="30")
        job = runner.launch(chosen.requests[0], "30", "/data", tmp_path)
        pid = runner.read_pid(job)

        # Act
        series.cancel(chosen)

        # Assert
        for _ in range(100):
            if not runner.is_alive(pid):
                break
            time.sleep(0.05)
        assert not runner.is_alive(pid)
        assert (job / runner.CANCELLED_FILE).is_file()
        assert series.state(chosen) == SeriesState.CANCELLED


class TestStop:
    def test_should_keep_the_results_and_launch_no_more_runs(self, tmp_path: Path, fake_tool):
        # Arrange: one run at a time, each too long to finish
        chosen = make(tmp_path, count=3, parallel=1, jar="30")
        driver = threading.Thread(
            target=series.drive, args=(chosen,), kwargs={"poll_seconds": 0.02}
        )
        driver.start()
        first = series.members(chosen)[0].run
        for _ in range(200):
            if first.results.is_dir():
                break
            time.sleep(0.02)

        # Act
        series.stop(chosen)
        driver.join(timeout=10)
        wait_until_it_ends(first)

        # Assert
        assert not driver.is_alive()
        assert states(chosen) == [runs.RunState.FINISHED.value] + [series.NOT_STARTED] * 2
        assert runs.stopped_by_user(first)
        assert series.state(chosen) == SeriesState.STOPPED_BY_USER


class TestTrash:
    @staticmethod
    def finished(tmp_path: Path) -> series.Series:
        chosen = make(tmp_path, count=2, parallel=2)
        series.drive(chosen, poll_seconds=0.02)
        for member in series.members(chosen):
            wait_until_it_ends(member.run)
        return chosen

    def test_should_move_every_run_and_restore_them(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = self.finished(tmp_path)

        # Act
        assert series.move_to_trash(chosen) == 2

        # Assert
        assert states(chosen) == [series.DELETED] * 2
        members = series.trashed_runs(chosen)
        assert len(members) == 2

        # Act
        for member in members:
            runs.restore(tmp_path, member)

        # Assert
        assert states(chosen) == ["finished", "finished"]
        assert [item.key for item in series.list_series(tmp_path)] == ["toy / s"]

    def test_should_refuse_a_series_that_is_running(self, tmp_path: Path):
        chosen = make(tmp_path)
        (chosen.directory / runner.PID_FILE).write_text(f"{os.getpid()}\n")
        with pytest.raises(ValueError, match="still running"):
            series.move_to_trash(chosen)

    def test_should_forget_a_series_only_when_nothing_is_left(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = self.finished(tmp_path)
        series.move_to_trash(chosen)

        # Act: still in the trash
        series.forget_deleted(tmp_path)

        # Assert
        assert chosen.directory.is_dir()

        # Act
        runs.empty_trash(tmp_path)
        series.forget_deleted(tmp_path)

        # Assert: the identifier can be used again
        assert not chosen.directory.exists()
        assert series.all_series(tmp_path) == []


class TestList:
    def test_should_map_runs_to_their_series(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = make(tmp_path, count=2, parallel=2)
        series.drive(chosen, poll_seconds=0.02)

        # Act & Assert
        assert [item.key for item in series.list_series(tmp_path)] == ["toy / s"]
        assert series.series_of_runs(tmp_path)[("toy", "s_seed_6")] == "s"

    def test_should_hide_a_series_whose_runs_were_deleted(self, tmp_path: Path, fake_tool):
        # Arrange
        chosen = make(tmp_path, count=2, parallel=2)
        series.drive(chosen, poll_seconds=0.02)
        for member in series.members(chosen):
            wait_until_it_ends(member.run)
            runs.move_to_trash(tmp_path, member.run)

        # Act & Assert
        assert states(chosen) == [series.DELETED] * 2
        assert series.list_series(tmp_path) == []
