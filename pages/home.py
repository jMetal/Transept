"""Home: what Transept is for, the example in one click, and the way through its three steps
(explore, optimize, analyze), each with its pages and its state. What it shows besides the links
comes from transept/home_panel.py."""

import streamlit as st

from transept import dataset_check, home_panel, runner, runs, settings, tutorials, ui
from transept.sections import SECTIONS, Page, Section

STEPS = ("Explore", "Optimize", "Analyze")
RECENT_RUNS = 4
STATE_BADGES = {
    runs.RunState.RUNNING: ("Running", ":material/sync:", "blue"),
    runs.RunState.FINISHED: ("Finished", ":material/check_circle:", "green"),
    runs.RunState.FAILED: ("Failed", ":material/error:", "red"),
    runs.RunState.CANCELLED: ("Cancelled", ":material/cancel:", "gray"),
    runs.RunState.INTERRUPTED: ("Interrupted", ":material/pause_circle:", "orange"),
}


def describe(run: runs.Run) -> str:
    """The algorithm and the dataset of a run, e.g. "NSGA-II on classF"."""
    algorithm = home_panel.algorithm_label(runs.config(run).get("algorithmType"))
    return f"{algorithm} on {run.dataset}"


def launch_example(current: settings.Settings) -> None:
    """Launches NSGA-II on the example dataset and follows it in the Monitor."""
    request = home_panel.example_request()
    runner.launch(request, current.jar, str(settings.EXAMPLES), settings.runs_root())
    ui.select_run(runs.run_of(settings.runs_root(), request.dataset, request.run_id))
    st.switch_page(ui.MONITOR)


def datasets_ready(current: settings.Settings) -> tuple[int, int]:
    """How many datasets there are, and in how many repositories."""
    entries = dataset_check.catalogue(settings.all_repositories(current))
    return len(entries), len({entry.repository.path for entry in entries})


def plural(count: int, noun: str, many: str | None = None) -> str:
    return f"{count} {noun if count == 1 else many or noun + 's'}"


def render_hero(current: settings.Settings, problems: list[str]) -> None:
    st.title("Transept: topology-aware alignment of transmembrane proteins")
    st.markdown("#### Alignments that keep every helix whole")
    st.markdown(
        "Transept searches alignments that agree with the topology and the AlphaFold2 structures "
        "of your proteins, and lets you compare the trade-offs it finds."
    )
    for problem in problems:
        st.error(problem)
    first, second, third, overview_column = st.columns([1, 1, 1, 1.3], vertical_alignment="center")
    if first.button(
        "Run the example",
        type="primary",
        icon=":material/rocket_launch:",
        width="stretch",
        disabled=bool(problems),
        help="NSGA-II with its defaults on the example dataset, followed in the Monitor. "
        "It takes one or two minutes.",
    ):
        launch_example(current)
    second.page_link(ui.NEW_RUN, label="New run", icon=":material/tune:", width="stretch")
    third.page_link(
        ui.ADD_DATASET, label="Add your proteins", icon=":material/add_circle:", width="stretch"
    )
    overview = tutorials.tutorial_named(tutorials.OVERVIEW)
    if overview is not None:
        overview_column.page_link(
            ui.tutorial_page(overview),
            label="New here? Read the overview",
            icon=":material/school:",
        )


def render_page(page: Page) -> None:
    """A page of a step: a link with what it offers, or a notice that it is coming."""
    with st.container(border=True):
        if page.available:
            st.page_link(page.path, label=page.title, icon=page.icon)
        else:
            st.markdown(f"{page.icon} **{page.title}** :gray-badge[Coming soon]")
        st.caption(page.description)


def render_recent(summary: home_panel.Activity) -> None:
    st.markdown("**Recent runs**")
    if not summary.recent:
        st.caption("No runs yet: run the example above, or open New run.")
        return
    for recent in summary.recent:
        label, icon, color = STATE_BADGES[recent.state]
        when = recent.launched.strftime("%d %b, %H:%M") if recent.launched else recent.run.run_id
        what, action = st.columns([5, 1], vertical_alignment="center")
        what.markdown(
            f"**{recent.algorithm}** on {recent.run.dataset}  \n"
            f":{color}-badge[{icon} {label}] :gray[{when}]"
        )
        done = recent.state == runs.RunState.FINISHED
        if action.button(
            "",
            key=f"home_open_{recent.run.key}",
            icon=":material/scatter_plot:" if done else ":material/monitoring:",
            help="Open in Results" if done else "Open in the Monitor",
            type="tertiary",
        ):
            ui.select_run(recent.run)
            st.switch_page(ui.RESULTS if done else ui.MONITOR)
    st.page_link(ui.HISTORY, label="All runs in History", icon=":material/history:")


def step_state(name: str, summary: home_panel.Activity, ready: tuple[int, int]) -> str:
    """What a step has now, in a few words."""
    if name == "Explore":
        datasets, repositories = ready
        return (
            f"{plural(datasets, 'dataset')} in {plural(repositories, 'repository', 'repositories')}"
        )
    if name == "Optimize":
        return (
            f"{summary.running} running · {plural(summary.total, 'run')} · "
            f"{plural(summary.series_count, 'series', 'series')}"
        )
    return f"{summary.finished} with results"


def render_step(
    number: int, section: Section, summary: home_panel.Activity, ready: tuple[int, int]
) -> None:
    st.subheader(f"{number} · {section.name}", anchor=False)
    st.caption(step_state(section.name, summary, ready))
    for page in section.pages:
        render_page(page)
    if section.name == "Optimize" and summary.active is not None:
        st.info(f"Running now: {describe(summary.active)}.")
        if st.button("Follow it in the Monitor", icon=":material/monitoring:"):
            ui.select_run(summary.active)
            st.switch_page(ui.MONITOR)
    if section.name == "Analyze":
        render_recent(summary)


def render_learn_and_more() -> None:
    """The tutorials, and what is coming in the other sections."""
    with st.container(border=True):
        st.markdown("**Learn**")
        found = tutorials.list_tutorials()
        if not found:
            st.caption("No tutorials found.")
        for column, tutorial in zip(st.columns(max(len(found), 1)), found):
            column.page_link(
                ui.tutorial_page(tutorial), label=tutorial.title, icon=":material/school:"
            )
    coming = [
        page
        for section in SECTIONS
        if section.name not in STEPS
        for page in section.pages
        if not page.available
    ]
    for page in coming:
        st.caption(f"{page.icon} Coming soon: **{page.title}**. {page.description}")


def render_settings(current: settings.Settings, problems: list[str]) -> None:
    with st.expander("Settings", expanded=bool(problems)):
        if not problems:
            st.caption(f"Ready: {home_panel.java_label(settings.java_version())}.")
        with st.form("settings"):
            jar = st.text_input("Transept core jar (with dependencies)", current.jar)
            if st.form_submit_button("Save"):
                settings.save_settings(settings.Settings(jar.strip(), current.repositories))
                st.rerun()
        st.page_link(
            ui.DATASETS, label="Add data directories in Datasets", icon=":material/dataset:"
        )
        st.caption(f"Runs are stored in {settings.runs_root()}.")


current = settings.load_settings()
problems = settings.problems(current)
summary = home_panel.activity(settings.runs_root(), limit=RECENT_RUNS)
ready = datasets_ready(current) if not problems else (0, 0)

render_hero(current, problems)
st.divider()
sections = {section.name: section for section in SECTIONS}
for number, (column, name) in enumerate(zip(st.columns(3, gap="large"), STEPS), start=1):
    with column:
        render_step(number, sections[name], summary, ready)
st.divider()
render_learn_and_more()
render_settings(current, problems)
