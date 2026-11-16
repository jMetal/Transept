"""Home: what Transept is for, the example in one click, the latest result, recent activity and
the way to every page. What it shows besides the links comes from transept/home_panel.py."""

import streamlit as st

from transept import charts, dataset_check, front, home_panel, runner, runs, settings, tutorials, ui
from transept.branding import MARK
from transept.sections import SECTIONS, Page, Section

CARDS_PER_ROW = 2
RECENT_RUNS = 4
PICTURE_HEIGHT = 330
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


def render_picture(summary: home_panel.Activity) -> None:
    """The run in progress, or else the front of the latest result, or else the logo."""
    if summary.active is not None:
        st.plotly_chart(
            charts.progress_figure(runs.progress(summary.active)).update_layout(
                height=PICTURE_HEIGHT
            ),
            config={"displayModeBar": False},
            width="stretch",
        )
        st.caption(f"In progress: {describe(summary.active)}.")
        if st.button("Follow it in the Monitor", icon=":material/monitoring:"):
            ui.select_run(summary.active)
            st.switch_page(ui.MONITOR)
        return
    latest = summary.latest_result
    values = runs.objective_values(latest) if latest is not None else None
    if latest is None or values is None or len(values.columns) != 2:
        st.image(MARK, width=240)
        return
    table = front.summarize(values)
    figure = charts.front_figure(values, table, front.knee_row(table))
    figure.update_layout(height=PICTURE_HEIGHT, margin={"l": 0, "r": 0, "t": 10, "b": 0})
    st.plotly_chart(figure, config={"displayModeBar": False}, width="stretch")
    st.caption(f"Latest result: {describe(latest)} ({latest.run_id}). The knee is marked.")
    if st.button("Open it in Results", icon=":material/scatter_plot:"):
        ui.select_run(latest)
        st.switch_page(ui.RESULTS)


def render_hero(current: settings.Settings, problems: list[str], summary) -> None:
    text, picture = st.columns([5, 4], vertical_alignment="center", gap="large")
    with text:
        st.title("Align transmembrane proteins without breaking a helix")
        st.markdown(
            "Transept searches alignments that agree with the topology and the AlphaFold2 "
            "structures of your proteins, and lets you compare the trade-offs it finds."
        )
        if problems:
            for problem in problems:
                st.error(problem)
        else:
            entries = dataset_check.catalogue(settings.all_repositories(current))
            noun = "dataset" if len(entries) == 1 else "datasets"
            holders = len({entry.repository.path for entry in entries})
            place = "repository" if holders == 1 else "repositories"
            st.caption(
                f"Ready: {home_panel.java_label(settings.java_version())} · {len(entries)} {noun} "
                f"in {holders} {place}"
            )
        first, second, third = st.columns(3)
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
            st.page_link(
                ui.tutorial_page(overview),
                label="New here? Read the overview",
                icon=":material/school:",
            )
    with picture:
        render_picture(summary)


def render_metrics(summary: home_panel.Activity) -> None:
    figures = [
        ("Runs", summary.total),
        ("With results", summary.finished),
        ("Running now", summary.running),
        ("Series", summary.series_count),
    ]
    for column, (label, value) in zip(st.columns(len(figures)), figures, strict=True):
        with column.container(border=True):
            st.metric(label, value)


def render_card(page: Page) -> None:
    with st.container(border=True, height="stretch"):
        st.markdown(f"#### {page.icon} {page.title}")
        st.markdown(page.description)
        if page.available:
            st.page_link(page.path, label=f"Open {page.title}", icon=":material/arrow_forward:")
        else:
            st.badge("Coming soon", icon=":material/construction:", color="gray")


def render_section(section: Section) -> None:
    pages = [page for page in section.pages if not page.is_tutorials]
    if not pages:
        return
    st.caption(section.name.upper())
    for start in range(0, len(pages), CARDS_PER_ROW):
        for column, page in zip(st.columns(CARDS_PER_ROW), pages[start : start + CARDS_PER_ROW]):
            with column:
                render_card(page)


def render_learn() -> None:
    st.subheader("Learn")
    with st.container(border=True):
        found = tutorials.list_tutorials()
        if not found:
            st.caption("No tutorials found.")
        for tutorial in found:
            st.page_link(ui.tutorial_page(tutorial), label=tutorial.title, icon=":material/school:")


def render_recent(summary: home_panel.Activity) -> None:
    st.subheader("Recent runs")
    with st.container(border=True):
        if not summary.recent:
            st.markdown(
                ":material/lightbulb: No runs yet: **Run the example** above, or open "
                "**New run** to choose a dataset and an algorithm."
            )
            return
        for recent in summary.recent:
            label, icon, color = STATE_BADGES[recent.state]
            when = recent.launched.strftime("%d %b, %H:%M") if recent.launched else ""
            what, action = st.columns([6, 1], vertical_alignment="center")
            what.markdown(
                f"**{recent.algorithm}** on {recent.run.dataset}  \n"
                f":{color}-badge[{icon} {label}] :gray[{when or recent.run.run_id}]"
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


def render_settings(current: settings.Settings, problems: list[str]) -> None:
    with st.expander("Settings", expanded=bool(problems)):
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

render_hero(current, problems, summary)
render_metrics(summary)
pages, side = st.columns([3, 2], gap="large")
with pages:
    st.subheader("Everything in Transept")
    for section in SECTIONS:
        render_section(section)
with side:
    render_learn()
    render_recent(summary)
render_settings(current, problems)
