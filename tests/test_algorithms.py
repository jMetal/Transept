"""The catalogue of algorithms of the jar."""

import json
import subprocess
from pathlib import Path

import pytest

from transept import algorithms, options

ENTRY = {
    "name": "NSGA_II",
    "minObjectives": 2,
    "maxObjectives": 3,
    "parameterSpace": "MSANSGAII.yaml",
    "steadyState": False,
    "asynchronous": False,
    "usesCrossover": True,
}


def algorithm(**changes) -> algorithms.Algorithm:
    return algorithms._parse(json.dumps([{**ENTRY, **changes}]))[0]


class TestAlgorithm:
    def test_should_describe_what_it_accepts(self):
        nsga = algorithm()
        assert nsga.objectives == "2-3"
        assert nsga.configurable
        assert nsga.formulations == ["SOPWTP_LDDT", "SOPWTP_LDDT_COVERAGE"]
        assert nsga.description == options.DESCRIPTIONS["NSGA_II"]

    def test_should_show_a_single_number_of_objectives(self):
        ga = algorithm(name="GENETIC_ALGORITHM", minObjectives=1, maxObjectives=1)
        assert ga.objectives == "1"
        assert ga.formulations == ["LDDT"]

    def test_should_use_the_name_of_an_unknown_algorithm(self):
        assert algorithm(name="NEW").description == "NEW"

    def test_should_warn_about_what_limits_it(self):
        notes = " ".join(
            algorithm(
                parameterSpace=None, steadyState=True, asynchronous=True, usesCrossover=False
            ).notes
        )
        assert "Only the mutation" in notes
        assert "does not repeat exactly" in notes
        assert "more threads do not speed it up" in notes
        assert "does not use the crossover" in notes

    def test_should_only_say_it_is_configurable_otherwise(self):
        assert algorithm().notes == ["Every parameter below can be set in **New run**."]


    def test_should_present_a_random_search_as_a_sanity_check(self):
        random_search = algorithm(name="RANDOM_SEARCH", parameterSpace=None, usesCrossover=False)
        assert "sanity check" in random_search.notes[0]
        assert "Only the mutation" not in " ".join(random_search.notes)


class TestCatalogue:
    def test_should_ask_the_jar_once_per_build(self, tmp_path: Path, monkeypatch):
        # Arrange
        jar = tmp_path / "tool.jar"
        jar.write_text("jar")
        calls = []

        def run(arguments, **options):
            calls.append(arguments)
            return subprocess.CompletedProcess(arguments, 0, json.dumps([ENTRY]), "")

        monkeypatch.setattr(subprocess, "run", run)

        # Act
        first = algorithms.catalogue(jar)
        second = algorithms.catalogue(jar)

        # Assert
        assert [item.name for item in first] == ["NSGA_II"]
        assert first == second
        assert len(calls) == 1
        assert calls[0][-2:] == [str(jar), "algorithms"]

    def test_should_report_a_missing_jar(self, tmp_path: Path):
        with pytest.raises(algorithms.CatalogueError, match="not found"):
            algorithms.catalogue(tmp_path / "gone.jar")

    @pytest.mark.parametrize(
        "behaviour",
        [
            lambda a, **o: subprocess.CompletedProcess(a, 0, "not json", ""),
            lambda a, **o: subprocess.CompletedProcess(a, 0, '[{"name": "X"}]', ""),
        ],
    )
    def test_should_report_an_unexpected_answer(self, tmp_path, monkeypatch, behaviour):
        jar = tmp_path / "tool.jar"
        jar.write_text("jar")
        monkeypatch.setattr(subprocess, "run", behaviour)
        with pytest.raises(algorithms.CatalogueError):
            algorithms.catalogue(jar)

    def test_should_report_a_failing_jar(self, tmp_path: Path, monkeypatch):
        def fail(arguments, **options):
            raise subprocess.CalledProcessError(1, arguments)

        jar = tmp_path / "tool.jar"
        jar.write_text("jar")
        monkeypatch.setattr(subprocess, "run", fail)
        with pytest.raises(algorithms.CatalogueError):
            algorithms.catalogue(jar)


class TestFormulationDetails:
    def test_should_explain_every_formulation(self):
        assert set(algorithms.FORMULATION_DETAILS) == set(options.OBJECTIVES)
