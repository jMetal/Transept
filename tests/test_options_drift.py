"""Drift detection: the options offered by the studio must match those of the Transept core jar.

The test reads the help of the `run` command of the jar configured for the studio (the sibling
repository or TRANSEPT_CORE_JAR) and is skipped when the jar or Java is not available.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from transept import options, runner, settings, spaces

JAR = settings.default_settings().jar

pytestmark = pytest.mark.skipif(
    not Path(JAR).is_file() or shutil.which("java") is None,
    reason="the Transept core jar or Java is not available",
)


@pytest.fixture(scope="module")
def run_help() -> str:
    result = subprocess.run(
        ["java", "-jar", JAR, "run", "--help"], capture_output=True, text=True, timeout=120
    )
    return " ".join(result.stdout.split())


def candidates(text: str, label: str) -> tuple[str, ...]:
    match = re.search(re.escape(label) + r": ([A-Z0-9_]+(?:, [A-Z0-9_]+)*)\.", text)
    assert match, f"'{label}' not found in the help of `run`"
    return tuple(match.group(1).split(", "))


@pytest.mark.parametrize(
    ("label", "offered"),
    [
        ("Search algorithm", options.ALGORITHMS),
        ("Mutation operator", options.MUTATIONS),
    ],
)
def test_should_offer_exactly_the_values_of_the_tool(run_help, label, offered):
    available = tuple(v for v in candidates(run_help, label) if v not in options.NOT_OFFERED)
    assert offered == available, (
        f"transept/options.py is out of step with the jar for '{label}'"
    )


def test_should_describe_every_value(run_help):
    for value in (
        *options.ALGORITHMS,
        *options.MUTATIONS,
    ):
        assert value in options.DESCRIPTIONS


def test_should_pass_only_options_that_the_tool_accepts(run_help):
    request = runner.RunRequest(
        dataset="classF", seeds=("mafft", "muscle5"), run_id="r", seed=1, mutation_probability=0.2
    )
    arguments = runner.command(request, JAR, "data", Path("runs"))
    for flag in (argument for argument in arguments if argument.startswith("--")):
        assert re.search(re.escape(flag) + r"\b", run_help), f"the jar does not accept {flag}"


def test_should_find_the_parameter_space_of_every_configurable_algorithm():
    for algorithm in spaces.PARAMETER_SPACES:
        assert spaces.parameter_space(JAR, algorithm), algorithm
        assert spaces.default_configuration(JAR, algorithm), algorithm


def test_should_offer_the_formulations_of_the_tool(run_help):
    assert set(options.OBJECTIVES) == set(candidates(run_help, "Objectives to optimise"))


def test_should_know_the_objectives_each_algorithm_accepts():
    result = subprocess.run(
        ["java", "-jar", JAR, "algorithms"], capture_output=True, text=True, timeout=120
    )
    for algorithm in json.loads(result.stdout):
        if algorithm["name"] in options.NOT_OFFERED:
            continue
        expected = (algorithm["minObjectives"], algorithm["maxObjectives"])
        assert options.objective_range(algorithm["name"]) == expected, algorithm["name"]
        assert (algorithm["parameterSpace"] is not None) == spaces.is_configurable(
            algorithm["name"]
        ), algorithm["name"]
