"""Builds the command of a run, launches it as a detached process and cancels it.

A run is launched with Transept core's `run` command. The tool writes its results to
`<runs-root>/ejecuciones/<dataset>/<run-id>/` and refuses to start if that directory exists, so
Transept keeps its own files about the job (request, PID, log, cancellation mark) apart, in
`<runs-root>/jobs/<dataset>/<run-id>/`.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from transept import options, settings, spaces

REQUEST_FILE = "request.json"
PID_FILE = "pid.txt"
LOG_FILE = "log.txt"
CANCELLED_FILE = "cancelled"
# Created in the results directory of a run, it makes the tool end the run and keep its results.
STOP_FILE = "STOP"


@dataclass(slots=True, frozen=True)
class RunRequest:
    """Everything a run needs besides the paths of the jar and the data.

    Attributes:
        dataset: Dataset name.
        seeds: Tools whose precomputed alignments seed the population.
        run_id: Identifier of the run, unique within the dataset.
        seed: Seed of the random generator.
        algorithm: Value of --algorithm.
        max_evaluations: Stopping criterion, unless `max_time` is given.
        population_size: Population size.
        threads: Evaluation threads.
        mutation: Value of --mutation.
        crossover: Value of --crossover.
        crossover_probability: Probability of the crossover.
        mutation_probability: Probability of the mutation; None for the default of the algorithm.
        progress_interval: Evaluations between progress records.
        configuration: For algorithms configured from a parameter space, the parameters that
            differ from the default configuration ("--name value ..."); the operator options
            are not passed for them.
        max_time: Stop after this many seconds instead of `max_evaluations`; None to stop by
            evaluations.
        objectives: Value of --objectives.
        repair_seeds: Whether the gaps inside helices are moved out of the precomputed seeds; the
            internal ones are always repaired.
        max_shift: Value of --max-shift, for algorithms not configured from a parameter space.
        cut_candidates: Value of --cut-candidates, likewise.
    """

    dataset: str
    seeds: tuple[str, ...]
    run_id: str
    seed: int
    algorithm: str = "NSGA_II"
    max_evaluations: int = options.DEFAULT_MAX_EVALUATIONS
    population_size: int = options.DEFAULT_POPULATION_SIZE
    threads: int = 1
    mutation: str = "TM_SAFE_GAP_SHIFT"
    crossover: str = options.DEFAULT_CROSSOVER
    crossover_probability: float = options.DEFAULT_CROSSOVER_PROBABILITY
    mutation_probability: float | None = None
    progress_interval: int = 100
    configuration: str = ""
    max_time: float | None = None
    objectives: str = options.DEFAULT_OBJECTIVES
    repair_seeds: bool = True
    max_shift: int = options.DEFAULT_MAX_SHIFT
    cut_candidates: int = options.DEFAULT_CUT_CANDIDATES


def validate(request: RunRequest) -> list[str]:
    """Lists the problems of a request that the tool would reject; empty if there are none."""
    found = []
    if not request.seeds:
        found.append("Choose at least one seed alignment.")
    elif (
        len(request.seeds) < 2
        and "internal" not in request.seeds
        and request.population_size > 1
        and request.algorithm != "PAES"
    ):
        found.append(
            "Choose at least two seed alignments: the rest of the population is made of "
            "their crossover children."
        )
    if not request.run_id or any(char in request.run_id for char in "/\\ "):
        found.append("The run identifier cannot be empty or contain spaces or slashes.")
    if request.max_evaluations < 1 or request.population_size < 1 or request.threads < 1:
        found.append("Evaluations, population size and threads must be positive.")
    if request.max_time is not None and request.max_time <= 0:
        found.append("The time limit must be positive.")
    if request.algorithm not in options.algorithms_for(request.objectives):
        found.append(f"{request.algorithm} does not accept the objectives {request.objectives}.")
    if (
        request.algorithm in options.NEED_WEIGHT_VECTORS
        and options.OBJECTIVES[request.objectives][1] == 3
        and request.population_size not in options.THREE_OBJECTIVE_SIZES
    ):
        sizes = ", ".join(str(size) for size in options.THREE_OBJECTIVE_SIZES)
        name = {"MOEA_D": "MOEA/D", "NSGA_III": "NSGA-III"}[request.algorithm]
        found.append(f"{name} with three objectives needs a population size of {sizes}.")
    return found


def run_directory(runs_root: Path, dataset: str, run_id: str) -> Path:
    """Returns the directory where the tool writes the results of a run."""
    return runs_root / "ejecuciones" / dataset / run_id


def job_directory(runs_root: Path, dataset: str, run_id: str) -> Path:
    """Returns the directory where Transept keeps its files about a run."""
    return runs_root / "jobs" / dataset / run_id


def command(request: RunRequest, jar: str, data_root: str, runs_root: Path) -> list[str]:
    """Returns the command line of a run."""
    arguments = [
        settings.java_command(),
        "-jar",
        str(jar),
        "run",
        "--data-root",
        str(data_root),
        "--dataset",
        request.dataset,
        "--seeds",
        ",".join(request.seeds),
        "--output-root",
        str(runs_root),
        "--run-id",
        request.run_id,
        "--seed",
        str(request.seed),
        "--algorithm",
        request.algorithm,
        "--population-size",
        str(request.population_size),
        "--threads",
        str(request.threads),
        "--progress-interval",
        str(request.progress_interval),
        "--objectives",
        request.objectives,
    ]
    # Always explicit: the default of the tool depends on its version.
    arguments.append("--repair-seeds" if request.repair_seeds else "--no-repair-seeds")
    if request.max_time is None:
        arguments += ["--max-evaluations", str(request.max_evaluations)]
    else:
        arguments += ["--max-time", f"{request.max_time:g}"]
    if spaces.is_configurable(request.algorithm):
        if request.configuration.strip():
            arguments += ["--configuration", request.configuration.strip()]
        return arguments
    arguments += [
        "--mutation",
        request.mutation,
        "--crossover-probability",
        str(request.crossover_probability),
    ]
    if request.crossover != options.DEFAULT_CROSSOVER:
        arguments += ["--crossover", request.crossover]
    if request.mutation_probability is not None:
        arguments += ["--mutation-probability", str(request.mutation_probability)]
    if request.max_shift != options.DEFAULT_MAX_SHIFT:
        arguments += ["--max-shift", str(request.max_shift)]
    if request.cut_candidates != options.DEFAULT_CUT_CANDIDATES:
        arguments += ["--cut-candidates", str(request.cut_candidates)]
    return arguments


def shell_command(arguments: list[str]) -> str:
    """Returns a command line that can be pasted into a shell."""
    return shlex.join(arguments)


def launch(request: RunRequest, jar: str, data_root: str, runs_root: Path) -> Path:
    """Starts a run in the background and returns its job directory.

    The process gets its own session, so that it survives the browser and Transept; its output
    goes to a log file, which tells why a run that never wrote its results did not start.

    Raises:
        FileExistsError: If the run identifier is already used in the dataset.
    """
    results = run_directory(runs_root, request.dataset, request.run_id)
    job = job_directory(runs_root, request.dataset, request.run_id)
    if results.exists() or job.exists():
        raise FileExistsError(f"Run '{request.run_id}' already exists in {request.dataset}")
    job.mkdir(parents=True)
    (job / REQUEST_FILE).write_text(json.dumps(asdict(request), indent=2) + "\n", encoding="utf-8")
    with (job / LOG_FILE).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command(request, jar, data_root, runs_root),
            cwd=job,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    (job / PID_FILE).write_text(f"{process.pid}\n", encoding="utf-8")
    # Reap the process when it ends, so that it is not mistaken for a live one.
    threading.Thread(target=process.wait, daemon=True).start()
    return job


def read_pid(job: Path) -> int | None:
    """Returns the PID of a job, or None if it has none."""
    try:
        return int((job / PID_FILE).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_alive(pid: int | None) -> bool:
    """Tells whether a process is running."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def request_stop(results: Path) -> bool:
    """Asks a running search to end now and keep its results.

    The tool creates the results directory when the run starts; until then there is nothing to
    stop, and creating the directory would make the run fail.

    Returns:
        Whether the request was made.
    """
    if not results.is_dir():
        return False
    (results / STOP_FILE).write_text("stopped by the user\n", encoding="utf-8")
    return True


def stop_requested(results: Path) -> bool:
    """Whether a stop was requested and the tool has not handled it yet."""
    return (results / STOP_FILE).is_file()


def cancel(job: Path) -> None:
    """Stops a running job and marks it as cancelled."""
    (job / CANCELLED_FILE).write_text("cancelled by the user\n", encoding="utf-8")
    pid = read_pid(job)
    if is_alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def request_from_dict(values: dict) -> RunRequest:
    """Returns a request saved as JSON; options of earlier versions are ignored."""
    values = {**values, "seeds": tuple(values["seeds"])}
    known = {name for name in RunRequest.__dataclass_fields__}
    return RunRequest(**{key: value for key, value in values.items() if key in known})


def read_request(job: Path) -> RunRequest | None:
    """Returns the request saved with a job, or None if there is none."""
    path = job / REQUEST_FILE
    if not path.is_file():
        return None
    return request_from_dict(json.loads(path.read_text(encoding="utf-8")))
