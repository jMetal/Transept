"""Plotly figures of Transept."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from transept.front import FIRST, SECOND

ALL_COLOUR = "#b7bcc5"
FRONT_COLOUR = "#1769aa"
SELECTED_COLOUR = "#d62728"


def progress_figure(records: pd.DataFrame) -> go.Figure:
    """Best value of each objective against the evaluations, one panel per objective."""
    names = [name for name in records.columns if name not in ("evaluations", "seconds")]
    figure = make_subplots(
        rows=1, cols=max(len(names), 1), subplot_titles=[f"Best {name}" for name in names]
    )
    for column, name in enumerate(names, start=1):
        figure.add_trace(
            go.Scatter(
                x=records["evaluations"],
                y=records[name],
                mode="lines",
                name=name,
                line={"color": FRONT_COLOUR},
            ),
            row=1,
            col=column,
        )
        figure.update_xaxes(title_text="Evaluations", row=1, col=column)
    figure.update_layout(showlegend=False, height=320, margin={"t": 40, "b": 40})
    return figure


def series_progress_figure(finished: list[pd.DataFrame], active: list[pd.DataFrame]) -> go.Figure:
    """Best value of each objective of several runs: the active ones stand out over the others.

    Args:
        finished: The progress records of the finished runs, in grey.
        active: The progress records of the runs in progress, in blue.
    """
    with_data = [records for records in [*active, *finished] if not records.empty]
    names = []
    if with_data:
        names = [c for c in with_data[0].columns if c not in ("evaluations", "seconds")]
    figure = make_subplots(
        rows=1, cols=max(len(names), 1), subplot_titles=[f"Best {name}" for name in names]
    )
    styles = (
        (finished, {"color": ALL_COLOUR, "width": 1}, 0.7),
        (active, {"color": FRONT_COLOUR, "width": 2.5}, 1.0),
    )
    for column, name in enumerate(names, start=1):
        for group, line, opacity in styles:  # the active runs last, so that they are on top
            for records in group:
                if not records.empty:
                    figure.add_trace(
                        go.Scatter(
                            x=records["evaluations"],
                            y=records[name],
                            mode="lines",
                            line=line,
                            opacity=opacity,
                            hoverinfo="x+y",
                        ),
                        row=1,
                        col=column,
                    )
        figure.update_xaxes(title_text="Evaluations", row=1, col=column)
    figure.update_layout(showlegend=False, height=320, margin={"t": 40, "b": 40})
    return figure


def series_front_figure(fronts: list[pd.DataFrame], aggregate: pd.DataFrame) -> go.Figure:
    """The front of each run in grey and their aggregate in blue.

    The solutions of the aggregate carry their seed and row as custom data, so that a click can
    open them.

    Args:
        fronts: The non-dominated solutions of each run, with the columns SOPwTP and lDDT.
        aggregate: The aggregate, with the columns `seed`, `row`, SOPwTP, lDDT and `note`; the
            solutions with a note are marked.
    """
    figure = go.Figure()
    for table in fronts:
        figure.add_trace(
            go.Scatter(
                x=table[FIRST],
                y=table[SECOND],
                mode="markers",
                marker={"color": ALL_COLOUR, "size": 6},
                opacity=0.7,
                hoverinfo="skip",
                showlegend=False,
            )
        )
    figure.add_trace(
        go.Scatter(
            x=aggregate[FIRST],
            y=aggregate[SECOND],
            mode="lines+markers",
            name="Aggregate",
            marker={"color": FRONT_COLOUR, "size": 8},
            line={"color": FRONT_COLOUR},
            customdata=aggregate[["seed", "row"]].to_numpy().tolist(),
            hovertemplate=f"seed %{{customdata[0]}}, MSASol%{{customdata[1]}}<br>{FIRST} %{{x}}<br>"
            f"{SECOND} %{{y:.4f}}<extra></extra>",
        )
    )
    marked = aggregate[aggregate["note"] != ""]
    figure.add_trace(
        go.Scatter(
            x=marked[FIRST],
            y=marked[SECOND],
            mode="markers+text",
            name="Extremes, knee",
            text=marked["note"],
            textposition="top right",
            marker={"color": FRONT_COLOUR, "size": 12, "symbol": "diamond"},
            customdata=marked[["seed", "row"]].to_numpy().tolist(),
            hoverinfo="skip",
        )
    )
    figure.update_layout(
        xaxis_title=FIRST,
        yaxis_title=SECOND,
        height=420,
        margin={"t": 20, "b": 40},
        showlegend=False,
    )
    return figure


SEED_COLOUR = "#2ca02c"
COMPROMISE_COLOUR = "#ff7f0e"


def front_figure(
    values: pd.DataFrame,
    front: pd.DataFrame,
    selected: int | None,
    seeds: pd.DataFrame | None = None,
    compromise: int | None = None,
) -> go.Figure:
    """All solutions, the non-dominated ones joined by a line, the seeds and the chosen ones.

    Every solution carries its row of FUN.csv as custom data, so that a click can select it.
    Seeds (columns `method`, SOPwTP, lDDT) carry no row and cannot be selected.
    """
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=values[FIRST],
            y=values[SECOND],
            mode="markers",
            name="All solutions",
            marker={"color": ALL_COLOUR, "size": 7},
            customdata=list(values.index),
            hovertemplate=f"MSASol%{{customdata}}<br>{FIRST} %{{x}}<br>"
            f"{SECOND} %{{y:.4f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=front[FIRST],
            y=front[SECOND],
            mode="lines+markers",
            name="Non-dominated",
            marker={"color": FRONT_COLOUR, "size": 8},
            line={"color": FRONT_COLOUR},
            customdata=list(front["row"]),
            hovertemplate=f"MSASol%{{customdata}}<br>{FIRST} %{{x}}<br>"
            f"{SECOND} %{{y:.4f}}<extra></extra>",
        )
    )
    marked = front[front["note"] != ""]
    figure.add_trace(
        go.Scatter(
            x=marked[FIRST],
            y=marked[SECOND],
            mode="markers+text",
            name="Extremes, knee",
            text=marked["note"],
            textposition="top right",
            marker={"color": FRONT_COLOUR, "size": 12, "symbol": "diamond"},
            customdata=list(marked["row"]),
            hoverinfo="skip",
        )
    )
    if seeds is not None and not seeds.empty:
        figure.add_trace(
            go.Scatter(
                x=seeds[FIRST],
                y=seeds[SECOND],
                mode="markers+text",
                name="Seed alignments",
                text=seeds["method"],
                textposition="bottom center",
                marker={"color": SEED_COLOUR, "size": 10, "symbol": "square"},
                hovertemplate=f"%{{text}}<br>{FIRST} %{{x}}<br>{SECOND} %{{y:.4f}}<extra></extra>",
            )
        )
    if compromise is not None and compromise in values.index:
        figure.add_trace(
            go.Scatter(
                x=[values.loc[compromise, FIRST]],
                y=[values.loc[compromise, SECOND]],
                mode="markers",
                name="Weighted compromise",
                marker={
                    "color": COMPROMISE_COLOUR,
                    "size": 18,
                    "symbol": "circle-open",
                    "line": {"width": 3},
                },
                customdata=[compromise],
                hoverinfo="skip",
            )
        )
    if selected is not None and selected in values.index:
        figure.add_trace(
            go.Scatter(
                x=[values.loc[selected, FIRST]],
                y=[values.loc[selected, SECOND]],
                mode="markers",
                name=f"MSASol{selected}",
                marker={"color": SELECTED_COLOUR, "size": 16, "symbol": "star"},
                customdata=[selected],
                hoverinfo="skip",
            )
        )
    figure.update_layout(
        xaxis_title=f"{FIRST} (higher is better)",
        yaxis_title=f"{SECOND} (higher is better)",
        height=480,
        margin={"t": 20},
        legend={"orientation": "h", "y": -0.2},
    )
    return figure


def identity_figure(identity, labels: list[str]) -> go.Figure:
    """Heat map of the pairwise identities of an alignment."""
    figure = go.Figure(
        go.Heatmap(
            z=identity,
            x=labels,
            y=labels,
            colorscale="Blues",
            zmin=0,
            zmax=1,
            colorbar={"title": "identity"},
        )
    )
    figure.update_layout(
        height=max(320, 12 * len(labels)), margin={"t": 20}, yaxis={"autorange": "reversed"}
    )
    return figure
