"""New run: choose the dataset, the seeds and the options, and launch the tool."""

import os
import random
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st

from transept import datasets, internal_seeds, options, runner, runs, settings, spaces, ui
from transept.configuration import (
    complete_values,
    configuration_string,
    modified_values,
    values_outside_the_space,
)
from transept.parameter_form import render_configuration_form

st.title("New run")

current = settings.load_settings()
if settings.problems(current):
    st.warning("Transept is not ready yet: check the settings.")
    st.page_link(ui.HOME, label="Go to the settings", icon=":material/home:")
    st.stop()


@st.cache_data(show_spinner=False)
def inspect_dataset(data_root: str, dataset: str, stamp: float):
    """Proteins, proteins without structure, and the valid and invalid seeds of a dataset."""
    proteins = datasets.read_topology(datasets.topology_file(data_root, dataset))
    problems = {
        tool: datasets.seed_problem(datasets.seed_file(data_root, dataset, tool), proteins)
        for tool in datasets.list_seed_tools(data_root, dataset)
    }
    valid = [tool for tool, problem in problems.items() if problem is None]
    invalid = {tool: problem for tool, problem in problems.items() if problem is not None}
    missing = datasets.proteins_without_structure(data_root, dataset, proteins)
    return proteins, missing, valid, invalid


def last_change(data_root: str, dataset: str) -> float:
    """Latest modification of the dataset's seeds, so that edited files are checked again."""
    directory = Path(data_root) / "precomputed" / dataset
    return max((path.stat().st_mtime for path in directory.glob("*.fasta")), default=0.0)


available = datasets.list_datasets(current.data_root)
default_dataset = available.index("classF") if "classF" in available else 0
dataset = st.selectbox("Dataset", available, index=default_dataset)
proteins, missing, tools, invalid = inspect_dataset(
    current.data_root, dataset, last_change(current.data_root, dataset)
)
mean_length = sum(len(protein.residues) for protein in proteins) / max(len(proteins), 1)
st.caption(
    f"{len(proteins)} proteins, {mean_length:.0f} residues on average. The cost of a run grows "
    "with the square of the number of proteins."
)
if missing:
    st.warning(
        f"{len(missing)} of {len(proteins)} proteins have no structure, so the lDDT ignores "
        f"them: {', '.join(missing)}."
    )
if invalid:
    with st.expander(f"{len(invalid)} seed alignments cannot be used with this dataset"):
        for tool, problem in invalid.items():
            st.markdown(f"- **{tool}**: {problem}")

seeds = st.multiselect(
    "Seed alignments",
    [internal_seeds.NAME, *tools],
    default=[internal_seeds.NAME],
    format_func=lambda value: (
        "internal (computed by the tool)" if value == internal_seeds.NAME else value
    ),
    help="Alignments that start the search: up to 10 computed by the tool itself (internal), "
    "and/or the precomputed alignments of other tools that match the sequences of the dataset.",
)
for tool in seeds:
    if tool in datasets.KNOWN_ISSUES:
        st.info(f"**{tool}**: {datasets.KNOWN_ISSUES[tool]}")
if internal_seeds.NAME in seeds:
    root = settings.runs_root()
    columns = st.columns([3, 1])
    stored = internal_seeds.ready(root, dataset)
    if internal_seeds.computing(root, dataset):
        columns[0].info("Computing the internal seeds of this dataset in the background...")
        if columns[1].button("Refresh"):
            st.rerun()
    elif stored:
        columns[0].caption(
            f"{stored} internal seeds of {dataset} are computed in advance; the run will read them."
        )
    else:
        columns[0].caption(
            "The internal seeds will be computed at the start of the run (seconds for 11-19 "
            "proteins, minutes for the largest datasets), or compute them now, once, for all "
            "the runs of this dataset."
        )
        if columns[1].button("Compute them now"):
            internal_seeds.launch(current.jar, current.data_root, root, dataset)
            st.rerun()
repair_seeds = st.checkbox(
    "Repair the seeds",
    value=False,
    help="Move the gaps that split a transmembrane helix out of every seed before the search. "
    "The operators never create such gaps, but keep those of the seeds.",
)

objectives = st.selectbox(
    "Objectives",
    list(options.OBJECTIVES),
    format_func=lambda value: options.OBJECTIVES[value][0],
    help="What the search optimises. The algorithms offered depend on the number of objectives.",
)
left, right = st.columns(2)
with left:
    algorithm = st.selectbox(
        "Algorithm",
        options.algorithms_for(objectives),
        format_func=lambda value: options.DESCRIPTIONS[value],
    )
    population_size = st.number_input(
        "Population size", 1, 10_000, options.DEFAULT_POPULATION_SIZE, step=4
    )
    threads = st.number_input(
        "Evaluation threads", 1, os.cpu_count() or 1, min(4, os.cpu_count() or 1)
    )
with right:
    stop_by = st.radio("Stop after", ["Evaluations", "Time"], horizontal=True)
    if stop_by == "Evaluations":
        max_evaluations = st.number_input(
            "Evaluations", 1, 10_000_000, options.DEFAULT_MAX_EVALUATIONS, step=500
        )
        max_time = None
    else:
        max_evaluations = options.DEFAULT_MAX_EVALUATIONS
        max_time = st.number_input(
            "Seconds",
            1.0,
            7 * 24 * 3600.0,
            60.0,
            step=10.0,
            help="Runs that stop by time do not repeat exactly with the same seed: the number of "
            "evaluations depends on the machine.",
        )

mutation = "TM_SAFE_GAP_SHIFT"
crossover_probability = options.DEFAULT_CROSSOVER_PROBABILITY
mutation_probability = options.default_mutation_probability(algorithm)
configuration = ""
parameters = None
if spaces.is_configurable(algorithm):
    try:
        parameters = spaces.parameter_space(current.jar, algorithm)
    except (KeyError, OSError, zipfile.BadZipFile):
        st.warning(
            "This build of Transept core has no parameter space for this algorithm: only the "
            "operator options are offered. Rebuild the jar to configure it."
        )
if parameters is not None:
    reference = {
        **spaces.default_configuration(current.jar, algorithm),
        "offspringPopulationSize": str(int(population_size)),
    }
    version = st.session_state.setdefault("configuration_version", 0)
    key_prefix = f"configuration_{algorithm}_{int(population_size)}_{version}"
    with st.expander("Configuration of the algorithm"):
        st.caption(
            "The parameter space of the algorithm in the tool, starting from its default "
            "(published) configuration; ✏️ marks what you changed. Set the population size "
            "first: changing it resets this form."
        )
        if st.button("Reset to the default configuration"):
            st.session_state["configuration_version"] = version + 1
            st.rerun()
        edited = render_configuration_form(
            parameters, complete_values(parameters, reference), reference, key_prefix
        )
    outside = values_outside_the_space(parameters, edited)
    if outside:
        st.warning("Outside the parameter space: " + ", ".join(f"`{name}`" for name in outside))
    changed = modified_values(parameters, edited, reference)
    configuration = " ".join(f"--{name} {edited[name]}" for name in changed)
    st.caption(
        f"{len(changed)} parameter(s) changed from the default configuration."
        if changed
        else "Default configuration."
    )
    with st.expander("Complete configuration"):
        st.code(configuration_string(parameters, edited), language=None, wrap_lines=True)
else:
    operators = st.columns(3)
    mutation = operators[0].selectbox(
        "Mutation", options.MUTATIONS, format_func=lambda value: options.DESCRIPTIONS[value]
    )
    crossover_probability = operators[1].slider(
        "Crossover probability", 0.0, 1.0, options.DEFAULT_CROSSOVER_PROBABILITY, 0.05
    )
    mutation_probability = operators[2].slider(
        "Mutation probability", 0.0, 1.0, options.default_mutation_probability(algorithm), 0.05
    )

if "random_seed" not in st.session_state:
    st.session_state["random_seed"] = random.randint(0, 999_999)
seed = st.number_input(
    "Random seed",
    0,
    2**31 - 1,
    key="random_seed",
    help="The same seed and options reproduce a run exactly.",
)
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
run_id = st.text_input("Run identifier", f"{algorithm.lower()}-{stamp}")

request = runner.RunRequest(
    dataset=dataset,
    seeds=tuple(seeds),
    run_id=run_id.strip(),
    seed=int(seed),
    algorithm=algorithm,
    max_evaluations=int(max_evaluations),
    population_size=int(population_size),
    threads=int(threads),
    mutation=mutation,
    crossover_probability=float(crossover_probability),
    mutation_probability=float(mutation_probability),
    configuration=configuration,
    max_time=None if max_time is None else float(max_time),
    objectives=objectives,
    repair_seeds=repair_seeds,
)
errors = runner.validate(request)
for error in errors:
    st.error(error)
if algorithm in options.ASYNCHRONOUS and threads > 1:
    st.info(
        "Asynchronous: every evaluated solution enters the population at once, so all threads stay "
        "busy, but the run will not repeat exactly with the same seed."
    )
if algorithm in options.STEADY_STATE and threads > 1:
    st.info("This algorithm evaluates one solution at a time: more threads will not speed it up.")

root = settings.runs_root()
with st.expander("Equivalent command line"):
    st.code(
        runner.shell_command(runner.command(request, current.jar, current.data_root, root)),
        language="bash",
    )

if st.button("Launch", type="primary", disabled=bool(errors)):
    try:
        runner.launch(request, current.jar, current.data_root, root)
    except FileExistsError as exception:
        st.error(str(exception))
    else:
        ui.select_run(runs.run_of(root, dataset, request.run_id))
        st.switch_page(ui.MONITOR)
