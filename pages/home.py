"""Home: what Transept is for, the example in one click, and the way through its three steps
(explore, optimize, analyze), each with its pages and its state. What it shows besides the links
comes from transept/home_panel.py."""

from dataclasses import replace

import streamlit as st

from transept import charts, dataset_check, front, home_panel, runner, runs, settings, tutorials, ui
from transept.branding import BLUE, MARK, NAVY, PALE_BLUE, RED, YELLOW
from transept.sections import SECTIONS, Page, Section

STEPS = ("Explore", "Optimize", "Analyze")
RECENT_RUNS = 4
PICTURE_HEIGHT = 320
# A few touches in the colours of the logo: a stripe as the flag (yellow, blue, red), the facts on
# a blue band, and the three steps on pale blue with a yellow edge. Containers with a key get the
# class st-key-<key>.
STYLE = f"""
<style>
.transept-flag {{
  height: 6px; border-radius: 3px; margin: 0.25rem 0 0.5rem;
  background: linear-gradient(to right, {YELLOW} 0 50%, {BLUE} 50% 75%, {RED} 75% 100%);
}}
.st-key-home_facts {{
  background: {BLUE}; border-radius: 0.9rem; padding: 1rem 1.25rem;
}}
.st-key-home_facts [data-testid="stMetric"] {{
  border-left: 4px solid {YELLOW}; padding-left: 0.75rem;
}}
.st-key-home_facts [data-testid="stMetricLabel"],
.st-key-home_facts [data-testid="stMetricLabel"] *,
.st-key-home_facts [data-testid="stMetricValue"] {{ color: #FFFFFF; }}
.st-key-home_facts [data-testid="stTooltipIcon"] svg {{
  stroke: rgba(255, 255, 255, 0.85) !important;
}}
[class*="st-key-home_step_"], [class*="st-key-home_learn_"] {{
  background: {PALE_BLUE}; border-top: 5px solid {YELLOW}; border-radius: 0.9rem;
  padding: 1rem 1rem 1.25rem;
}}
[class*="st-key-home_page_"] {{ background: #FFFFFF; }}
.transept-step {{
  display: flex; align-items: center; gap: 0.6rem; font-family: "Space Grotesk", sans-serif;
  font-size: 1.5rem; font-weight: 600; color: {NAVY};
}}
.transept-step span {{
  display: inline-flex; align-items: center; justify-content: center; width: 2.1rem;
  height: 2.1rem; border-radius: 50%; background: {BLUE}; color: {YELLOW}; font-size: 1.1rem;
}}
</style>
"""
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


def result_figure(run: runs.Run):
    """The result of a run, small: its front with the knee, in 3D with three objectives, or its
    convergence with one."""
    values = runs.objective_values(run)
    if len(values.columns) == 1 or values.empty:
        return charts.progress_figure(runs.progress(run))
    table = front.summarize(values)
    knee = front.knee_row(table)
    if len(values.columns) == 3:
        return charts.front3d_figure(values, table, knee)
    return charts.front_figure(values, table, knee)


def render_picture(summary: home_panel.Activity) -> None:
    """The run in progress, or else the result of the latest run, or else the logo."""
    run = summary.active or summary.latest_result
    if run is None:
        st.image(MARK, width=220)
        return
    active = run is summary.active
    figure = charts.progress_figure(runs.progress(run)) if active else result_figure(run)
    figure.update_layout(height=PICTURE_HEIGHT, margin={"l": 0, "r": 0, "t": 10, "b": 0})
    st.plotly_chart(figure, config={"displayModeBar": False}, width="stretch")
    if active:
        st.caption(f"In progress: {describe(run)}.")
        if st.button("Follow it in the Monitor", icon=":material/monitoring:"):
            ui.select_run(run)
            st.switch_page(ui.MONITOR)
    else:
        st.caption(f"Latest result: {describe(run)} ({run.run_id}). The knee is marked.")
        if st.button("Open it in Results", icon=":material/scatter_plot:"):
            ui.select_run(run)
            st.switch_page(ui.RESULTS)


def render_facts(ready: tuple[int, int]) -> None:
    facts = home_panel.project_facts(*ready, len(tutorials.list_tutorials()))
    st.html('<div class="transept-flag"></div>')
    with st.container(key="home_facts"):
        for column, fact in zip(st.columns(len(facts)), facts, strict=True):
            column.metric(fact.label, fact.value, help=fact.detail)


def render_hero(current: settings.Settings, problems: list[str], summary) -> None:
    text, picture = st.columns([5, 4], vertical_alignment="center", gap="large")
    with text:
        render_presentation(current, problems)
    with picture:
        render_picture(summary)


def render_presentation(current: settings.Settings, problems: list[str]) -> None:
    st.title("Transept: topology-aware alignment of transmembrane proteins")
    st.markdown("#### Alignments guided by membrane topology and AlphaFold structures")
    st.markdown(
        "Transept searches alignments that agree with the topology and the AlphaFold2 structures "
        "of your proteins, and lets you compare the trade-offs it finds."
    )
    for problem in problems:
        st.error(problem)
    first, second, third = st.columns(3, vertical_alignment="center")
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


def render_page(page: Page) -> None:
    """A page of a step: a link with what it offers, or a notice that it is coming."""
    slug = "".join(letter if letter.isalnum() else "_" for letter in page.title.lower())
    with st.container(border=True, key=f"home_page_{slug}"):
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
    with st.container(key=f"home_step_{number}"):
        st.html(f'<div class="transept-step"><span>{number}</span>{section.name}</div>')
        st.caption(step_state(section.name, summary, ready))
        for page in section.pages:
            render_page(page)
        if section.name == "Optimize" and summary.active is not None:
            st.info(f"Running now: {describe(summary.active)}. It is drawn at the top of the page.")
        if section.name == "Analyze":
            render_recent(summary)


def render_tutorial(item: tutorials.Tutorial | tutorials.Planned) -> None:
    """A tutorial of Learn: a link with what it is for, marked if it is still coming."""
    coming = isinstance(item, tutorials.Planned)
    slug = "".join(letter if letter.isalnum() else "_" for letter in item.name)
    with st.container(border=True, key=f"home_page_tutorial_{slug}"):
        st.page_link(
            ui.learning_page(item),
            label=item.title,
            icon=":material/schedule:" if coming else ":material/school:",
        )
        if coming:
            st.markdown(":gray-badge[Coming soon]")
        if item.summary:
            st.caption(item.summary)


def render_learn_and_more() -> None:
    """The tutorials by level, as the three steps, and what is coming in the other sections."""
    st.subheader("Learn", anchor=False)
    found = tutorials.learning_path()
    if not found:
        st.caption("No tutorials found.")
    groups = tutorials.by_level(found)
    for number, (column, (level, items)) in enumerate(
        zip(st.columns(len(groups), gap="large"), groups.items()), start=1
    ):
        with column, st.container(key=f"home_learn_{number}"):
            st.html(f'<div class="transept-step"><span>{number}</span>{level}</div>')
            for item in items:
                render_tutorial(item)
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
                settings.save_settings(replace(current, jar=jar.strip()))
                st.rerun()
        ui.expert_mode_toggle(current)
        st.page_link(
            ui.DATASETS, label="Add data directories in Datasets", icon=":material/dataset:"
        )
        st.caption(f"Runs are stored in {settings.runs_root()}.")


current = settings.load_settings()
problems = settings.problems(current)
summary = home_panel.activity(settings.runs_root(), limit=RECENT_RUNS)
ready = datasets_ready(current) if not problems else (0, 0)

st.html(STYLE)
render_hero(current, problems, summary)
render_facts(ready)
sections = {section.name: section for section in SECTIONS}
for number, (column, name) in enumerate(zip(st.columns(3, gap="large"), STEPS), start=1):
    with column:
        render_step(number, sections[name], summary, ready)
st.divider()
render_learn_and_more()
render_settings(current, problems)
