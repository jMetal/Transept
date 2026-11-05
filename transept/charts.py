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
