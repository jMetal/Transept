from pathlib import Path

import pytest

from transept import datasets, settings


class TestLocations:
    def test_should_keep_the_runs_in_the_transept_home(self, transept_home: Path):
        assert settings.runs_root() == transept_home / "runs"

    def test_should_default_to_the_examples_and_a_jar_found_nearby(
        self, transept_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.delenv(settings.JAR_VARIABLE, raising=False)

        # Act
        defaults = settings.default_settings()

        # Assert: relative to the repository, not to the home
        assert defaults.repositories == []
        assert settings.all_repositories(defaults) == [
            settings.Repository(settings.EXAMPLES_NAME, str(settings.EXAMPLES))
        ]
        assert defaults.jar in [str(path) for path in settings.jar_candidates()]

    def test_should_prefer_the_first_jar_that_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.delenv(settings.JAR_VARIABLE, raising=False)
        missing, present = tmp_path / "lib" / "a.jar", tmp_path / "core" / "a.jar"
        present.parent.mkdir()
        present.write_bytes(b"")
        monkeypatch.setattr(settings, "jar_candidates", lambda: [missing, present])

        # Act & Assert
        assert settings.default_jar() == str(present)

    def test_should_default_to_lib_when_no_jar_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.delenv(settings.JAR_VARIABLE, raising=False)
        candidates = [tmp_path / "lib" / "a.jar", tmp_path / "core" / "a.jar"]
        monkeypatch.setattr(settings, "jar_candidates", lambda: candidates)

        # Act & Assert
        assert settings.default_jar() == str(candidates[0])

    def test_should_find_datasets_in_the_examples(self):
        assert "classT2_19" in datasets.list_datasets(settings.EXAMPLES)

    def test_should_take_the_jar_from_the_environment(
        self, transept_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.setenv(settings.JAR_VARIABLE, "/somewhere/tool.jar")

        # Act & Assert
        assert settings.default_settings().jar == "/somewhere/tool.jar"


class TestJava:
    def test_should_prefer_the_java_of_java_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: a Java home that is not on the PATH, as in the Conda environment
        java = tmp_path / "jvm" / "bin" / "java"
        java.parent.mkdir(parents=True)
        java.write_text("#!/bin/sh\n")
        java.chmod(0o755)
        monkeypatch.setenv("JAVA_HOME", str(tmp_path / "jvm"))

        # Act & Assert
        assert settings.java_command() == str(java)

    def test_should_use_the_path_when_java_home_has_no_java(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.setenv("JAVA_HOME", str(tmp_path / "nothing"))
        monkeypatch.setattr(settings.shutil, "which", lambda name: f"/usr/bin/{name}")

        # Act & Assert
        assert settings.java_command() == "/usr/bin/java"


class TestPersistence:
    def test_should_load_what_was_saved(self, transept_home: Path):
        # Arrange
        chosen = settings.Settings("/a.jar", [settings.Repository("Mine", "/data")])
        settings.save_settings(chosen)

        # Act
        loaded = settings.load_settings()

        # Assert
        assert loaded == chosen

    def test_should_load_the_defaults_when_nothing_was_saved(self, transept_home: Path):
        assert settings.load_settings() == settings.default_settings()


class TestProblems:
    def test_should_report_nothing_when_everything_is_in_place(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        assert settings.problems(configured) == []

    def test_should_report_a_missing_jar_and_data_directory(self, transept_home: Path):
        # Act
        found = settings.problems(settings.Settings("/no.jar"))

        # Assert
        assert any("jar was not found" in problem for problem in found)
        assert any("No data directory is available" in problem for problem in found)
