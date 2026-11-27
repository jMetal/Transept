import dataclasses
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from transept import runner, settings

REQUEST = runner.RunRequest(dataset="toy", seeds=("mafft", "kalign"), run_id="r1", seed=7)


class TestValidation:
    def test_should_accept_a_valid_request(self):
        assert runner.validate(REQUEST) == []

    @pytest.mark.parametrize(
        ("changes", "message"),
        [
            ({"seeds": ()}, "at least one seed"),
            ({"seeds": ("mafft",)}, "at least two seed"),
            ({"run_id": "a b"}, "identifier"),
            ({"threads": 0}, "positive"),
            ({"max_time": 0.0}, "time limit"),
        ],
    )
    def test_should_report_what_the_tool_would_reject(self, changes, message):
        # Act
        found = runner.validate(dataclasses.replace(REQUEST, **changes))

        # Assert
        assert any(message in problem for problem in found)

    def test_should_accept_a_single_seed_for_paes(self):
        request = runner.RunRequest(
            dataset="toy", seeds=("mafft",), run_id="p", seed=1, algorithm="PAES"
        )
        assert runner.validate(request) == []


class TestCommand:
    def test_should_pass_every_option_to_the_tool(self, tmp_path: Path):
        # Act
        arguments = runner.command(REQUEST, "/t.jar", "/data", tmp_path)

        # Assert
        assert arguments[:4] == [settings.java_command(), "-jar", "/t.jar", "run"]
        options = dict(zip(arguments[4::2], arguments[5::2]))
        assert options["--seeds"] == "mafft,kalign"
        assert options["--output-root"] == str(tmp_path)
        assert options["--algorithm"] == "NSGA_II"
        assert "--mutation-probability" not in options

    def test_should_pass_the_settings_of_the_operators_only_when_they_change(self, tmp_path: Path):
        # Arrange
        default = replace(REQUEST, algorithm="PAES", objectives="SOPWTP_LDDT")
        changed = replace(default, max_shift=10, cut_candidates=8, crossover="TM_SAFE_UNIFORM")

        # Act
        before = runner.command(default, "/t.jar", "/data", tmp_path)
        after = runner.command(changed, "/t.jar", "/data", tmp_path)

        # Assert: earlier builds of the tool do not know these options
        assert "--max-shift" not in before and "--cut-candidates" not in before
        assert "--crossover" not in before
        assert after[after.index("--crossover") + 1] == "TM_SAFE_UNIFORM"
        assert after[after.index("--max-shift") + 1] == "10"
        assert after[after.index("--cut-candidates") + 1] == "8"

    def test_should_pass_an_explicit_mutation_probability(self, tmp_path: Path):
        # Arrange: NSGA-II takes its operators from its configuration instead
        request = runner.RunRequest(
            dataset="toy",
            seeds=("a", "b"),
            run_id="r",
            seed=1,
            algorithm="SMS_EMOA",
            mutation_probability=0.5,
        )

        # Act
        arguments = runner.command(request, "/t.jar", "/data", tmp_path)

        # Assert
        assert arguments[-2:] == ["--mutation-probability", "0.5"]

    def test_should_pass_only_the_configuration_to_nsga_ii(self, tmp_path: Path):
        # Arrange
        request = dataclasses.replace(
            REQUEST, configuration="--selection random", mutation_probability=0.5
        )

        # Act
        arguments = runner.command(request, "/t.jar", "/data", tmp_path)

        # Assert
        assert arguments[-2:] == ["--configuration", "--selection random"]
        assert "--mutation" not in arguments
        assert "--mutation-probability" not in arguments

    def test_should_stop_by_time_when_asked(self, tmp_path: Path):
        # Act
        arguments = runner.command(
            dataclasses.replace(REQUEST, max_time=90.0), "/t.jar", "/data", tmp_path
        )

        # Assert
        assert "--max-time" in arguments
        assert arguments[arguments.index("--max-time") + 1] == "90"
        assert "--max-evaluations" not in arguments

    def test_should_quote_the_shell_command(self):
        assert runner.shell_command(["java", "a b"]) == "java 'a b'"


class TestLaunch:
    @pytest.fixture
    def fake_tool(self, monkeypatch: pytest.MonkeyPatch):
        """Replaces the tool by a Python process that sleeps for the given seconds."""

        def fake_command(request, jar, data_root, runs_root):
            return [sys.executable, "-c", f"import time; print('started'); time.sleep({jar})"]

        monkeypatch.setattr(runner, "command", fake_command)

    def test_should_save_the_request_and_follow_the_process(self, tmp_path: Path, fake_tool):
        # Act
        job = runner.launch(REQUEST, "0.2", "/data", tmp_path)

        # Assert
        assert runner.read_request(job) == REQUEST
        pid = runner.read_pid(job)
        assert runner.is_alive(pid)
        for _ in range(50):
            if not runner.is_alive(pid):
                break
            time.sleep(0.1)
        assert not runner.is_alive(pid)
        assert "started" in (job / runner.LOG_FILE).read_text()

    def test_should_refuse_an_identifier_already_used(self, tmp_path: Path, fake_tool):
        # Arrange
        runner.launch(REQUEST, "0", "/data", tmp_path)

        # Act & Assert
        with pytest.raises(FileExistsError):
            runner.launch(REQUEST, "0", "/data", tmp_path)

    def test_should_ask_the_tool_to_stop_only_once_the_run_has_started(self, tmp_path: Path):
        results = tmp_path / "ejecuciones" / "toy" / "r"
        assert not runner.request_stop(results)
        assert not results.exists()
        results.mkdir(parents=True)
        assert runner.request_stop(results)
        assert runner.stop_requested(results)

    def test_should_cancel_a_running_job(self, tmp_path: Path, fake_tool):
        # Arrange
        job = runner.launch(REQUEST, "30", "/data", tmp_path)
        pid = runner.read_pid(job)

        # Act
        runner.cancel(job)

        # Assert
        for _ in range(50):
            if not runner.is_alive(pid):
                break
            time.sleep(0.1)
        assert not runner.is_alive(pid)
        assert (job / runner.CANCELLED_FILE).is_file()

    def test_should_report_no_pid_and_no_request_for_an_unknown_job(self, tmp_path: Path):
        assert runner.read_pid(tmp_path) is None
        assert runner.read_request(tmp_path) is None
        assert not runner.is_alive(None)


def test_should_read_requests_saved_by_earlier_versions(tmp_path: Path):
    # Arrange: earlier versions saved a crossover option that no longer exists
    (tmp_path / runner.REQUEST_FILE).write_text(
        '{"dataset": "toy", "seeds": ["a", "b"], "run_id": "old", "seed": 1,'
        ' "crossover": "TWO_POINT"}'
    )

    # Act
    request = runner.read_request(tmp_path)

    # Assert
    assert request.run_id == "old"
