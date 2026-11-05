"""Parameter spaces and default configurations of the configurable algorithms of the tool.

Transept core builds some algorithms with Evolver from a parameter space in YAML and a default
configuration, both packaged in its jar. They are read from the jar, so Transept always offers
the parameters of the build that runs them.
"""

from __future__ import annotations

import functools
import zipfile
from pathlib import Path

from transept.configuration import parse_configuration
from transept.parameter_space import ParameterSpec, parse_parameter_space

# Algorithms of the tool built from a parameter space, and the space's file in the jar.
PARAMETER_SPACES = {
    "NSGA_II": "MSANSGAII.yaml",
    "SPEA2": "MSASPEA2.yaml",
    "GENETIC_ALGORITHM": "MSAGA.yaml",
}


def is_configurable(algorithm: str) -> bool:
    """Whether the algorithm is configured from a parameter space."""
    return algorithm in PARAMETER_SPACES


def parameter_space(jar: str | Path, algorithm: str) -> list[ParameterSpec]:
    """Returns the parameter space of a configurable algorithm.

    Raises:
        KeyError: If the algorithm has no parameter space, or the jar does not contain it.
    """
    entry = f"parameterSpaces/{_space(algorithm)}"
    return parse_parameter_space(_entry(*_key(jar), entry))


def default_configuration(jar: str | Path, algorithm: str) -> dict[str, str]:
    """Returns the default configuration of a configurable algorithm, by parameter name."""
    name = _space(algorithm).replace(".yaml", "Default.txt")
    return parse_configuration(_entry(*_key(jar), f"defaultConfigurations/{name}"))


def _space(algorithm: str) -> str:
    if algorithm not in PARAMETER_SPACES:
        raise KeyError(f"{algorithm} is not configured from a parameter space")
    return PARAMETER_SPACES[algorithm]


def _key(jar: str | Path) -> tuple[str, float]:
    path = Path(jar)
    return str(path), path.stat().st_mtime


@functools.lru_cache(maxsize=32)
def _entry(jar: str, mtime: float, entry: str) -> str:
    """Reads a text entry of the jar; the modification time makes a rebuilt jar be read again."""
    with zipfile.ZipFile(jar) as archive:
        try:
            return archive.read(entry).decode("utf-8")
        except KeyError as exception:
            raise KeyError(f"{entry} is not in {jar}") from exception
