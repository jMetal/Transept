"""Internal seeds computed in advance, as the studio sees them."""

import dataclasses
from pathlib import Path

from transept import internal_seeds, runner


class TestInternalSeeds:
    def test_should_count_the_seeds_of_the_manifest(self, tmp_path: Path):
        # Arrange
        directory = internal_seeds.directory(tmp_path, "toy")
        directory.mkdir(parents=True)
        (directory / internal_seeds.MANIFEST).write_text(
            "format\t1\ndataset\ttoy\nseed\tbiojava-g20x2\ta.fasta\tx\nseed\tbiojava-g30x2\tb.fasta\ty\n"
        )

        # Act & Assert
        assert internal_seeds.ready(tmp_path, "toy") == 2
        assert internal_seeds.ready(tmp_path, "other") == 0
        assert not internal_seeds.computing(tmp_path, "toy")

    def test_should_build_the_command_of_the_tool(self, tmp_path: Path):
        command = internal_seeds.command("/t.jar", "/data", tmp_path, "toy")
        assert command[3] == "seeds"
        assert command[command.index("--datasets") + 1] == "toy"
        assert command[command.index("--output-root") + 1] == str(tmp_path)


class TestRequests:
    def test_should_accept_internal_seeds_alone_and_pass_the_repair(self, tmp_path: Path):
        # Arrange
        request = runner.RunRequest(
            dataset="toy", seeds=("internal",), run_id="r", seed=1, repair_seeds=True
        )

        # Act
        arguments = runner.command(request, "/t.jar", "/data", tmp_path)

        # Assert
        assert runner.validate(request) == []
        assert "--repair-seeds" in arguments
        assert arguments[arguments.index("--seeds") + 1] == "internal"
        assert "--repair-seeds" not in runner.command(
            dataclasses.replace(request, repair_seeds=False), "/t.jar", "/data", tmp_path
        )
