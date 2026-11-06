"""What the jar can optimise with: the catalogue of its `algorithms` command, and what it means."""

from __future__ import annotations

import functools
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from transept import options, settings

TIMEOUT_SECONDS = 60

# What each formulation of --objectives optimises, for the user (see metrics.md of Transept core).
FORMULATION_DETAILS = {
    "SOPWTP_LDDT": "The default. SOPwTP is a sum of pairs that takes the topology into account, "
    "and the lDDT measures the structural consistency with the distances of the structures. The "
    "search returns a set of alignments that trade one for the other.",
    "LDDT": "Structural consistency alone, for the genetic algorithms and the random searches. "
    "The lDDT is a mean over the aligned residues, so it does not take into account how many "
    "residues are aligned. The search tends to return very similar alignments.",
    "SOPWTP_LDDT_COVERAGE": "Adds the aligned-pair coverage, which measures how much the alignment "
    "aligns, not whether it aligns the right residues, and complements the lDDT.",
}

# The operators outside the parameter spaces (see the tutorial T2 of Transept core).
CROSSOVER = (
    "Single-point crossover: combines two alignments with a cut that never splits a transmembrane "
    "helix. It is the only crossover, and it creates no gaps inside helices."
)


class CatalogueError(Exception):
    """The jar could not give its catalogue of algorithms."""


@dataclass(slots=True, frozen=True)
class Algorithm:
    """An algorithm of the jar, as its `algorithms` command describes it.

    Attributes:
        name: Its value in `run --algorithm`.
        min_objectives: The smallest number of objectives it accepts.
        max_objectives: The largest number of objectives it accepts.
        parameter_space: The file of its parameter space; None if it is not configurable.
        steady_state: Whether it evaluates one solution at a time.
        asynchronous: Whether solutions enter the population as soon as they are evaluated.
        uses_crossover: Whether it uses the crossover.
    """

    name: str
    min_objectives: int
    max_objectives: int
    parameter_space: str | None
    steady_state: bool
    asynchronous: bool
    uses_crossover: bool

    @property
    def description(self) -> str:
        return options.DESCRIPTIONS.get(self.name, self.name)

    @property
    def objectives(self) -> str:
        low, high = self.min_objectives, self.max_objectives
        return str(low) if low == high else f"{low}-{high}"

    @property
    def configurable(self) -> bool:
        return self.parameter_space is not None

    @property
    def parallel(self) -> bool:
        """Whether several evaluation threads speed it up."""
        return not self.steady_state

    @property
    def formulations(self) -> list[str]:
        """The formulations of --objectives it accepts."""
        return [
            name
            for name, (_, count) in options.OBJECTIVES.items()
            if self.min_objectives <= count <= self.max_objectives
        ]

    @property
    def notes(self) -> list[str]:
        """What is worth knowing before using it."""
        found = []
        if self.name in options.RANDOM_SEARCHES:
            found.append("A sanity check, to compare other algorithms with.")
        elif self.configurable:
            found.append("Every parameter below can be set in **New run**.")
        else:
            found.append("Only the mutation and the probabilities can be set in **New run**.")
        if self.asynchronous:
            found.append(
                "With more than one thread, a run does not repeat exactly with the same seed."
            )
        if self.steady_state:
            found.append(
                "It is not parallel: it evaluates one solution at a time, so more threads do not "
                "speed it up."
            )
        if not self.uses_crossover:
            found.append("It does not use the crossover.")
        return found


def _parse(text: str) -> tuple[Algorithm, ...]:
    return tuple(
        Algorithm(
            entry["name"],
            entry["minObjectives"],
            entry["maxObjectives"],
            entry.get("parameterSpace"),
            entry["steadyState"],
            entry["asynchronous"],
            entry["usesCrossover"],
        )
        for entry in json.loads(text)
    )


@functools.lru_cache(maxsize=4)
def _catalogue(jar: str, modified: float) -> tuple[Algorithm, ...]:
    """Asks the jar once; the modification time makes a rebuilt jar be asked again."""
    command = [settings.java_command(), "-jar", jar, "algorithms"]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, check=True
        )
        return _parse(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
        raise CatalogueError(str(error)) from error


def catalogue(jar: str | Path) -> tuple[Algorithm, ...]:
    """Returns the algorithms of a jar.

    Raises:
        CatalogueError: If the jar does not exist or does not give them.
    """
    path = Path(jar)
    if not path.is_file():
        raise CatalogueError(f"The jar was not found at {jar}")
    return _catalogue(str(path), path.stat().st_mtime)
