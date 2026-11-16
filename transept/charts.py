"""Plotly figures of Transept."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from transept.front import FIRST, SECOND

# The colours of the logo: membrane for the front, amber for what is chosen, ink for the seeds.
ALL_COLOUR = "#B7C3CC"
FRONT_COLOUR = "#1F7A8C"
SELECTED_COLOUR = "#C77D0A"


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


SEED_COLOUR = "#12324A"
COMPROMISE_COLOUR = "#8A5300"


def front_figure(
    values: pd.DataFrame,
    front: pd.DataFrame,
    selected: int | None,
    seeds: pd.DataFrame | None = None,
    compromise: int | None = None,
    first: str = FIRST,
    second: str = SECOND,
    connect: bool = True,
) -> go.Figure:
    """All solutions, the non-dominated ones joined by a line, the seeds and the chosen ones.

    Every solution carries its row of FUN.csv as custom data, so that a click can select it.
    Seeds (columns `method` and objectives) carry no row and cannot be selected; they are drawn
    only if they have both objectives of the chart.

    Args:
        first: The objective of the horizontal axis.
        second: The objective of the vertical axis.
        connect: Whether to join the non-dominated solutions by a line; not for the projection of a
            front of three objectives, whose points are not in order on two of them.
    """
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=values[first],
            y=values[second],
            mode="markers",
            name="All solutions",
            marker={"color": ALL_COLOUR, "size": 7},
            customdata=list(values.index),
            hovertemplate=f"MSASol%{{customdata}}<br>{first} %{{x}}<br>"
            f"{second} %{{y:.4f}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=front[first],
            y=front[second],
            mode="lines+markers" if connect else "markers",
            name="Non-dominated",
            marker={"color": FRONT_COLOUR, "size": 8},
            line={"color": FRONT_COLOUR},
            customdata=list(front["row"]),
            hovertemplate=f"MSASol%{{customdata}}<br>{first} %{{x}}<br>"
            f"{second} %{{y:.4f}}<extra></extra>",
        )
    )
    marked = front[front["note"] != ""]
    figure.add_trace(
        go.Scatter(
            x=marked[first],
            y=marked[second],
            mode="markers+text",
            name="Extremes, knee",
            text=marked["note"],
            textposition="top right",
            marker={"color": FRONT_COLOUR, "size": 12, "symbol": "diamond"},
            customdata=list(marked["row"]),
            hoverinfo="skip",
        )
    )
    if seeds is not None and not seeds.empty and {first, second} <= set(seeds.columns):
        figure.add_trace(
            go.Scatter(
                x=seeds[first],
                y=seeds[second],
                mode="markers+text",
                name="Seed alignments",
                text=seeds["method"],
                textposition="bottom center",
                marker={"color": SEED_COLOUR, "size": 10, "symbol": "square"},
                hovertemplate=f"%{{text}}<br>{first} %{{x}}<br>{second} %{{y:.4f}}<extra></extra>",
            )
        )
    if compromise is not None and compromise in values.index:
        figure.add_trace(
            go.Scatter(
                x=[values.loc[compromise, first]],
                y=[values.loc[compromise, second]],
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
                x=[values.loc[selected, first]],
                y=[values.loc[selected, second]],
                mode="markers",
                name=f"MSASol{selected}",
                marker={"color": SELECTED_COLOUR, "size": 16, "symbol": "star"},
                customdata=[selected],
                hoverinfo="skip",
            )
        )
    figure.update_layout(
        xaxis_title=f"{first} (higher is better)",
        yaxis_title=f"{second} (higher is better)",
        height=480,
        margin={"t": 20},
        legend={"orientation": "h", "y": -0.2},
    )
    return figure


def front3d_figure(values: pd.DataFrame, front: pd.DataFrame, selected: int | None) -> go.Figure:
    """The solutions of three objectives in 3D: all, the non-dominated, the extremes and knee, and
    the chosen one. It can be rotated, but not clicked: the solutions are chosen elsewhere."""
    names = list(values.columns)
    x, y, z = names

    def trace(data: pd.DataFrame, rows: list, name: str, marker: dict, **extra) -> go.Scatter3d:
        return go.Scatter3d(
            x=data[x], y=data[y], z=data[z], name=name, marker=marker, customdata=rows,
            hovertemplate=f"MSASol%{{customdata}}<br>{x} %{{x}}<br>{y} %{{y:.4f}}<br>"
            f"{z} %{{z:.4f}}<extra></extra>",
            **{"mode": "markers", **extra},
        )  # fmt: skip

    figure = go.Figure()
    figure.add_trace(
        trace(values, list(values.index), "All solutions", {"color": ALL_COLOUR, "size": 3})
    )
    figure.add_trace(
        trace(front, list(front["row"]), "Non-dominated", {"color": FRONT_COLOUR, "size": 4})
    )
    marked = front[front["note"] != ""]
    figure.add_trace(
        trace(
            marked, list(marked["row"]), "Extremes, knee",
            {"color": FRONT_COLOUR, "size": 7, "symbol": "diamond"},
            mode="markers+text", text=marked["note"],
        )
    )  # fmt: skip
    if selected is not None and selected in values.index:
        figure.add_trace(
            trace(
                values.loc[[selected]], [selected], f"MSASol{selected}",
                {"color": SELECTED_COLOUR, "size": 8},
            )
        )  # fmt: skip
    figure.update_layout(
        height=560,
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        legend={"orientation": "h", "y": -0.05},
        scene={
            "xaxis_title": x,
            "yaxis_title": y,
            "zaxis_title": z,
        },
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
