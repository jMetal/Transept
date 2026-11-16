"""The superposed structures as a 3D chart of their Cα traces, without Streamlit."""

from __future__ import annotations

import plotly.graph_objects as go

from transept.superposition import PlacedStructure

PALETTE = ("#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#76b7b2", "#edc948", "#ff9da7", "#9c755f")
OTHER_COLOUR = "#c8c8c8"
HIGHLIGHT = "#FFD100"
OUTLINE = "#14213D"


def _trace(
    item: PlacedStructure, numbers: list[int], keep: set[int], column_of: dict[int, int]
) -> tuple[list, list, list, list[str]]:
    """Returns the coordinates of the residues kept, with a break between separate stretches."""
    xs, ys, zs, texts = [], [], [], []
    previous = None
    for number in numbers:
        if number not in keep:
            continue
        if previous is not None and number != previous + 1:
            xs.append(None), ys.append(None), zs.append(None), texts.append("")
        x, y, z = item.rotation @ item.structure.coordinates[number] + item.shift
        xs.append(x), ys.append(y), zs.append(z)
        column = column_of.get(number)
        where = f"column {column + 1}" if column is not None else "not aligned"
        texts.append(f"{item.structure.id} residue {number}, {where}")
        previous = number
    return xs, ys, zs, texts


def figure(
    placed: list[PlacedStructure], column: int | None, show_others: bool, height: int = 650
) -> go.Figure:
    """Draws each structure as a line through its Cα atoms, with its helices in its colour.

    Args:
        placed: The structures, already superposed.
        column: A column whose residues are marked, or None.
        show_others: Whether to draw the residues outside the membrane, in grey.
        height: The height of the chart, in pixels.
    """
    chart = go.Figure()
    for index, item in enumerate(placed):
        structure = item.structure
        numbers = sorted(structure.coordinates)
        column_of = {number: c for c, number in structure.columns.items()}
        helices = {structure.columns[c] for c in structure.transmembrane}
        colour = PALETTE[index % len(PALETTE)]
        if show_others:
            xs, ys, zs, texts = _trace(item, numbers, set(numbers), column_of)
            chart.add_trace(
                go.Scatter3d(
                    x=xs, y=ys, z=zs, text=texts, mode="lines", hoverinfo="text",
                    line={"color": OTHER_COLOUR, "width": 2}, legendgroup=structure.id,
                    showlegend=False, opacity=0.5,
                )
            )  # fmt: skip
        xs, ys, zs, texts = _trace(item, numbers, helices, column_of)
        chart.add_trace(
            go.Scatter3d(
                x=xs, y=ys, z=zs, text=texts, mode="lines", hoverinfo="text",
                line={"color": colour, "width": 6}, name=structure.id, legendgroup=structure.id,
            )
        )  # fmt: skip
    if column is not None:
        points = [(item, item.position(column)) for item in placed]
        points = [(item, point) for item, point in points if point is not None]
        if points:
            chart.add_trace(
                go.Scatter3d(
                    x=[p[0] for _, p in points], y=[p[1] for _, p in points],
                    z=[p[2] for _, p in points], mode="markers", hoverinfo="text",
                    text=[f"{item.structure.id}, column {column + 1}" for item, _ in points],
                    marker={"color": HIGHLIGHT, "size": 6, "line": {"color": OUTLINE, "width": 1}},
                    name=f"column {column + 1}",
                )
            )  # fmt: skip
    axis = {"visible": False}
    chart.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        scene={"xaxis": axis, "yaxis": axis, "zaxis": axis, "aspectmode": "data"},
        legend={"itemsizing": "constant"},
    )
    return chart
