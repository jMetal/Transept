import json
import os
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

    def test_should_find_the_newest_built_jar_whatever_its_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: no jar in lib/, two versions built in a sibling transept-core
        monkeypatch.delenv(settings.JAR_VARIABLE, raising=False)
        monkeypatch.setattr(settings, "REPOSITORY", tmp_path / "Transept")
        target = tmp_path / "transept-core" / "target"
        target.mkdir(parents=True)
        old = target / "transept-core-0.1.0-jar-with-dependencies.jar"
        new = target / "transept-core-0.1-SNAPSHOT-jar-with-dependencies.jar"
        for age, jar in enumerate([new, old]):
            jar.write_bytes(b"")
            os.utime(jar, (1000 - age, 1000 - age))

        # Act & Assert
        assert settings.default_jar() == str(new)

    def test_should_prefer_the_jar_copied_to_lib(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange
        monkeypatch.delenv(settings.JAR_VARIABLE, raising=False)
        monkeypatch.setattr(settings, "REPOSITORY", tmp_path / "Transept")
        lib = tmp_path / "Transept" / "lib"
        lib.mkdir(parents=True)
        (lib / "transept-core-0.1.0-jar-with-dependencies.jar").write_bytes(b"")
        (lib / settings.JAR_NAME).write_bytes(b"")

        # Act & Assert
        assert settings.default_jar() == str(lib / settings.JAR_NAME)

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

    def test_should_replace_a_saved_jar_of_lib_with_the_current_one(
        self, transept_home: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: settings saved with the jar of an earlier version in lib/
        monkeypatch.setenv(settings.JAR_VARIABLE, "/current/tool.jar")
        old = settings.REPOSITORY / "lib" / "transept-core-0.1.0-jar-with-dependencies.jar"
        settings.settings_file().write_text(json.dumps({"jar": str(old)}), encoding="utf-8")

        # Act & Assert
        assert settings.load_settings().jar == "/current/tool.jar"

    def test_should_turn_an_earlier_data_directory_into_a_repository(self, transept_home: Path):
        # Arrange
        settings.settings_file().write_text(
            '{"jar": "/a.jar", "data_root": "/benchmark/GPCRdb"}', encoding="utf-8"
        )

        # Act
        loaded = settings.load_settings()

        # Assert
        assert loaded.jar == "/a.jar"
        assert loaded.repositories == [settings.Repository("benchmark", "/benchmark/GPCRdb")]

    def test_should_not_add_the_examples_as_an_earlier_repository(self, transept_home: Path):
        # Arrange
        settings.settings_file().write_text(
            json.dumps({"jar": "/a.jar", "data_root": str(settings.EXAMPLES)}), encoding="utf-8"
        )

        # Act & Assert
        assert settings.load_settings().repositories == []

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


class TestRepositories:
    def test_should_add_a_directory_with_the_layout(self, transept_home: Path, data_root: Path):
        # Act
        chosen = settings.add_repository(settings.Settings("/a.jar"), str(data_root), "Mine")

        # Assert
        assert chosen.repositories == [settings.Repository("Mine", str(data_root))]

    def test_should_name_a_repository_after_its_folder(self):
        assert settings.default_repository_name("/benchmark/GPCRdb") == "benchmark"
        assert settings.default_repository_name("/my/proteins") == "proteins"

    def test_should_refuse_a_directory_without_the_layout(self, transept_home, tmp_path: Path):
        with pytest.raises(ValueError, match="does not look like a data directory"):
            settings.add_repository(settings.Settings("/a.jar"), str(tmp_path))

    def test_should_refuse_a_repeated_path_or_name(self, transept_home, data_root: Path, tmp_path):
        # Arrange
        chosen = settings.add_repository(settings.Settings("/a.jar"), str(data_root), "Mine")
        other = tmp_path / "other"
        (other / "sequences" / "tmregions").mkdir(parents=True)

        # Act & Assert
        with pytest.raises(ValueError, match="already the repository Mine"):
            settings.add_repository(chosen, str(data_root), "Another")
        with pytest.raises(ValueError, match="already a repository called Mine"):
            settings.add_repository(chosen, str(other), "Mine")

    def test_should_only_forget_a_removed_repository(self, transept_home, data_root: Path):
        # Arrange
        chosen = settings.add_repository(settings.Settings("/a.jar"), str(data_root))

        # Act
        chosen = settings.remove_repository(chosen, str(data_root))

        # Assert
        assert chosen.repositories == []
        assert data_root.is_dir()


class TestMyDatasets:
    def test_should_appear_once_it_has_datasets(self, transept_home: Path):
        # Arrange
        chosen = settings.Settings("/a.jar")
        names = [repository.name for repository in settings.all_repositories(chosen)]
        assert settings.MY_DATASETS_NAME not in names

        # Act
        (settings.datasets_root() / "sequences" / "tmregions").mkdir(parents=True)

        # Assert
        mine = settings.all_repositories(chosen)[1]
        assert mine == settings.Repository(settings.MY_DATASETS_NAME, str(settings.datasets_root()))
        assert settings.is_built_in(mine)

    def test_should_keep_its_name_for_itself(self, transept_home: Path, data_root: Path):
        with pytest.raises(ValueError, match="name of a repository of Transept"):
            settings.add_repository(
                settings.Settings("/a.jar"), str(data_root), settings.MY_DATASETS_NAME
            )


class TestDataRootOfRun:
    def test_should_prefer_the_directory_the_run_recorded(self, configured, data_root: Path):
        assert settings.data_root_of_run(configured, str(data_root), "other") == str(data_root)

    def test_should_look_for_the_dataset_when_the_directory_is_gone(self, configured, data_root):
        assert settings.data_root_of_run(configured, "/gone", "toy") == str(data_root)
        assert settings.data_root_of_run(configured, None, "toy") == str(data_root)

    def test_should_keep_what_was_recorded_when_no_repository_has_it(self, configured):
        assert settings.data_root_of_run(configured, "/gone", "other") == "/gone"
        assert settings.data_root_of_run(configured, None, "other") == ""


class TestPatience:
    @pytest.mark.parametrize("saved", [{}, {"patience": 0}, {"patience": "many"}])
    def test_should_use_the_default_without_a_valid_value(self, transept_home: Path, saved):
        settings.settings_file().write_text(json.dumps({"jar": "/a.jar", **saved}))
        assert settings.load_settings().patience == settings.DEFAULT_PATIENCE

    def test_should_survive_the_changes_of_repositories(self, data_root: Path):
        current = settings.Settings("/a.jar", patience=12)
        added = settings.add_repository(current, str(data_root), "Mine")
        assert added.patience == 12
        assert settings.remove_repository(added, str(data_root)).patience == 12


class TestExpertMode:
    def test_should_be_off_by_default_and_in_earlier_settings(self, transept_home: Path):
        assert not settings.default_settings().expert_mode
        settings.settings_file().write_text(json.dumps({"jar": "/a.jar"}))
        assert not settings.load_settings().expert_mode

    def test_should_survive_the_changes_of_repositories(self, data_root: Path):
        # Arrange
        current = settings.Settings("/a.jar", expert_mode=True)

        # Act
        added = settings.add_repository(current, str(data_root), "Mine")
        removed = settings.remove_repository(added, str(data_root))

        # Assert
        assert added.expert_mode and removed.expert_mode
        assert removed.repositories == []
