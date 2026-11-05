"""Reading the parameter spaces and default configurations from the jar of the tool."""

from pathlib import Path

import pytest
from conftest import write_fake_jar

from transept import spaces
from transept.configuration import complete_values, configuration_string, modified_values
from transept.parameter_space import CategoricalParameter


class TestSpaces:
    def test_should_read_the_space_and_default_of_nsga_ii(self, tmp_path: Path):
        # Arrange
        jar = tmp_path / "tool.jar"
        write_fake_jar(jar)

        # Act
        parameters = spaces.parameter_space(jar, "NSGA_II")
        defaults = spaces.default_configuration(jar, "NSGA_II")

        # Assert
        names = [parameter.name for parameter in parameters]
        assert names == [
            "algorithmResult",
            "createInitialSolutions",
            "offspringPopulationSize",
            "variation",
            "selection",
        ]
        assert defaults["mutation"] == "tmSafeGapShift"
        assert defaults["crossoverProbability"] == "0.8"
        assert isinstance(parameters[0], CategoricalParameter)

    def test_should_pass_only_the_changed_parameters(self, tmp_path: Path):
        # Arrange
        jar = tmp_path / "tool.jar"
        write_fake_jar(jar)
        parameters = spaces.parameter_space(jar, "NSGA_II")
        reference = spaces.default_configuration(jar, "NSGA_II")
        values = complete_values(parameters, reference)

        # Act
        values["selection"] = "random"
        values["algorithmResult"] = "externalArchive"
        changed = modified_values(parameters, values, reference)

        # Assert: the archive's sub-parameters are new, so they count as changed
        assert changed == [
            "algorithmResult",
            "populationSizeWithArchive",
            "archiveType",
            "selection",
        ]
        assert "--selectionTournamentSize" not in configuration_string(parameters, values)

    def test_should_read_the_space_of_spea2(self, tmp_path: Path):
        # Arrange
        jar = tmp_path / "tool.jar"
        write_fake_jar(jar)

        # Act
        names = [parameter.name for parameter in spaces.parameter_space(jar, "SPEA2")]
        defaults = spaces.default_configuration(jar, "SPEA2")

        # Assert
        assert {"ranking", "densityEstimator", "replacement"} <= set(names)
        assert defaults["ranking"] == "strengthRanking"

    def test_should_say_which_algorithms_are_configurable(self, tmp_path: Path):
        assert spaces.is_configurable("NSGA_II")
        assert spaces.is_configurable("SPEA2")
        assert not spaces.is_configurable("SMS_EMOA")
        with pytest.raises(KeyError):
            spaces.parameter_space(tmp_path / "missing.jar", "SMS_EMOA")
