"""What the home page shows besides its links: recent activity, the latest result, and the example.

Kept apart from the page (pages/home.py) so that it can be tested without Streamlit.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from transept import datasets, options, runner, runs, series, settings

EXAMPLE_DATASET: Final = "classT2_19"
_STAMP: Final = re.compile(r"(\d{8}-\d{6})")
ALGORITHM_LABELS: Final = {
    "NSGA_II": "NSGA-II",
    "ASYNC_NSGA_II": "Asynchronous NSGA-II",
    "SPEA2": "SPEA2",
    "GENETIC_ALGORITHM": "Genetic algorithm",
    "ASYNC_GENETIC_ALGORITHM": "Asynchronous genetic algorithm",
    "NSGA_III": "NSGA-III",
    "AGE_MOEA": "AGE-MOEA",
    "AGE_MOEA_II": "AGE-MOEA-II",
    "SMS_EMOA": "SMS-EMOA",
    "MOEA_D": "MOEA/D",
    "PAES": "PAES",
    "RANDOM_SEARCH": "Random search",
    "RANDOM_SEEDED": "Seeded random search",
}


@dataclass(slots=True, frozen=True)
class RecentRun:
    """A run as the home page lists it.

    Attributes:
        run: The run.
        state: Its state now.
        algorithm: Its algorithm, as the menu names it.
        launched: When it was launched, from its identifier, if it has a time stamp.
    """

    run: runs.Run
    state: runs.RunState
    algorithm: str
    launched: datetime | None


@dataclass(slots=True, frozen=True)
class Activity:
    """The runs and series of Transept, summarised.

    Attributes:
        recent: The newest runs, newest first.
        total: How many runs there are.
        by_state: How many runs are in each state.
        series_count: How many series there are.
        active: The newest run still running, if any.
        latest_result: The newest finished run, if any.
    """

    recent: tuple[RecentRun, ...]
    total: int
    by_state: dict[runs.RunState, int]
    series_count: int
    active: runs.Run | None
    latest_result: runs.Run | None

    @property
    def finished(self) -> int:
        """How many runs left results."""
        return self.by_state.get(runs.RunState.FINISHED, 0)

    @property
    def running(self) -> int:
        """How many runs are running now."""
        return self.by_state.get(runs.RunState.RUNNING, 0)


def algorithm_label(algorithm: str | None) -> str:
    """The name of an algorithm for people, e.g. "NSGA-II" for NSGA_II."""
    if not algorithm:
        return "Unknown algorithm"
    return ALGORITHM_LABELS.get(algorithm, algorithm.replace("_", "-"))


def java_label(version: str | None) -> str:
    """A short name of the Java found, e.g. "Java 21" for 'openjdk version "21.0.10" ...'."""
    match = re.search(r'version "(\d+)', version or "")
    return f"Java {match.group(1)}" if match else (version or "Java not found")


def launched_at(run_id: str) -> datetime | None:
    """When a run was launched, from the time stamp in its identifier (e.g. 20261110-120940)."""
    match = _STAMP.search(run_id)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None


def activity(runs_root: Path, limit: int = 4) -> Activity:
    """The activity under `runs_root`: its newest `limit` runs and counts of all of them."""
    every = runs.list_runs(runs_root)
    states = {run.key: runs.state(run) for run in every}
    recent = tuple(
        RecentRun(
            run=run,
            state=states[run.key],
            algorithm=algorithm_label(runs.config(run).get("algorithmType")),
            launched=launched_at(run.run_id),
        )
        for run in every[:limit]
    )
    return Activity(
        recent=recent,
        total=len(every),
        by_state=dict(Counter(states.values())),
        series_count=len(series.list_series(runs_root)),
        active=next((run for run in every if states[run.key] == runs.RunState.RUNNING), None),
        latest_result=next(
            (run for run in every if states[run.key] == runs.RunState.FINISHED), None
        ),
    )


def example_request(now: datetime | None = None) -> runner.RunRequest:
    """NSGA-II with its defaults on the example dataset, seeded with its precomputed alignments.

    The precomputed seeds let it start at once, without computing internal seeds first.
    """
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    tools = datasets.list_seed_tools(settings.EXAMPLES, EXAMPLE_DATASET)
    return runner.RunRequest(
        dataset=EXAMPLE_DATASET,
        seeds=tuple(datasets.default_seed_tools(tools)),
        run_id=f"example-{stamp}",
        seed=1,
        algorithm="NSGA_II",
        max_evaluations=options.DEFAULT_MAX_EVALUATIONS,
        population_size=options.DEFAULT_POPULATION_SIZE,
        threads=min(4, os.cpu_count() or 1),
    )


@dataclass(slots=True, frozen=True)
class Fact:
    """A figure about what Transept offers, for the row under the title of the home page.

    Attributes:
        label: What it counts.
        value: The figure.
        detail: A short explanation, shown on hover.
    """

    label: str
    value: str
    detail: str


def project_facts(datasets: int, repositories: int, tutorials: int) -> list[Fact]:
    """What Transept offers: its datasets, algorithms, formulations, operators and tutorials."""
    places = "repository" if repositories == 1 else "repositories"
    return [
        Fact("Datasets", str(datasets), f"In {repositories} {places}, ready to align"),
        Fact(
            "Algorithms",
            str(len(options.ALGORITHMS)),
            "NSGA-II, SPEA2, a genetic algorithm and others, with two random searches as checks",
        ),
        Fact(
            "Formulations",
            str(len(options.OBJECTIVES)),
            "Objectives to optimise: SOPwTP and lDDT, lDDT alone, or both with coverage",
        ),
        Fact(
            "Operators",
            str(len(options.CROSSOVERS) + len(options.MUTATIONS)),
            f"{len(options.CROSSOVERS)} crossovers and {len(options.MUTATIONS)} mutations, none "
            "of them breaks a helix",
        ),
        Fact("Tutorials", str(tutorials), "Guides inside Transept, in Learn"),
    ]
