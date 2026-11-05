from pathlib import Path

import pytest

from transept import datasets, settings


class TestLocations:
    def test_should_keep_the_runs_in_the_studio_home(self, studio_home: Path):
        assert settings.runs_root() == studio_home / "runs"

    def test_should_default_to_the_examples_and_a_jar_found_nearby(
        self, studio_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.delenv(settings.JAR_VARIABLE, raising=False)

        # Act
        defaults = settings.default_settings()

        # Assert: relative to the repository, not to the home
        assert defaults.data_root == str(settings.REPOSITORY / "examples" / "GPCRdb")
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
        self, studio_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.setenv(settings.JAR_VARIABLE, "/somewhere/tool.jar")

        # Act & Assert
        assert settings.default_settings().jar == "/somewhere/tool.jar"


class TestPersistence:
    def test_should_load_what_was_saved(self, studio_home: Path):
        # Arrange
        settings.save_settings(settings.Settings(jar="/a.jar", data_root="/data"))

        # Act
        loaded = settings.load_settings()

        # Assert
        assert loaded == settings.Settings(jar="/a.jar", data_root="/data")

    def test_should_load_the_defaults_when_nothing_was_saved(self, studio_home: Path):
        assert settings.load_settings() == settings.default_settings()


class TestProblems:
    def test_should_report_nothing_when_everything_is_in_place(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        assert settings.problems(configured) == []

    def test_should_report_a_missing_jar_and_data_directory(self, studio_home: Path):
        # Act
        found = settings.problems(settings.Settings(jar="/no.jar", data_root="/no/data"))

        # Assert
        assert any("jar was not found" in problem for problem in found)
        assert any("does not look like a data directory" in problem for problem in found)
