"""Streamlit form to adjust a configuration within a parameter space.

Adapted from Evolver-Studio (evolver_studio/parameter_form.py, render_configuration_form), by the
same authors.
"""

import math
from collections.abc import Mapping

import streamlit as st

from transept.configuration import same_value
from transept.options import PARAMETER_HELP
from transept.parameter_space import (
    CategoricalParameter,
    ParameterRow,
    ParameterSpec,
    RangeParameter,
    active_sub_parameters,
    filter_rows,
    parameter_rows,
    summarize_parameter_space,
)

CONFIGURATION_FORM_COLUMNS = 3
MODIFIED_MARK = " ✏️"


def render_parameter_space_table(parameters: list[ParameterSpec], key: str) -> None:
    """Render a parameter space as a read-only table, one row per parameter.

    Above the table, a one-line summary of the size of the space and a filter by text. Each
    sub-parameter is indented under its parent, and "Active if" says when it applies. Filtering
    keeps the ancestors of every match.

    Args:
        parameters: The top-level parameters to render.
        key: Prefix for widget keys, unique per table on the page.
    """
    summary = summarize_parameter_space(parameters)
    st.markdown(
        f"**{summary.total}** parameters · **{summary.top_level}** top-level · "
        f"**{summary.categorical}** categorical · **{summary.numeric}** numeric · "
        f"maximum depth **{summary.max_depth}**"
    )
    text = st.text_input(
        "Filter parameters",
        key=f"{key}_filter",
        placeholder="Name, value or condition (e.g. mutation, archive)",
    )
    rows = filter_rows(parameter_rows(parameters), text)
    if not rows:
        st.info(f'No parameter matches "{text}".')
        return
    st.dataframe([_table_row(row) for row in rows], hide_index=True, width="stretch")


def _table_row(row: ParameterRow) -> dict[str, str]:
    # Non-breaking spaces: the table would trim ordinary leading ones.
    indent = "\u00a0" * 5 * (row.depth - 1) + "\u00a0└\u00a0" if row.depth else ""
    return {
        "Parameter": f"{indent}{row.name}",
        "Type": row.kind,
        "Active if": row.condition,
        "Domain": row.domain,
    }


def render_configuration_form(
    parameters: list[ParameterSpec],
    values: Mapping[str, str],
    reference: Mapping[str, str],
    key_prefix: str,
) -> dict[str, str]:
    """Render a form to adjust a configuration within a parameter space.

    One widget per *active* parameter, filled with the configuration's value and limited to what
    the space allows: a selector with a categorical parameter's values, a number input with a range
    parameter's bounds. A parameter's sub-parameters appear and disappear with its value, and a
    parameter whose value differs from the reference configuration is marked. A value the space
    does not allow is shown as it is, flagged, not corrected in silence.

    Args:
        parameters: The top-level parameters of the space.
        values: A value for every parameter of the space, as `configuration.complete_values` gives.
        reference: The configuration to mark changes against, typically the default one.
        key_prefix: Prefix for widget keys, unique per form instance; a new prefix resets the form
            to `values`.

    Returns:
        The values after the user's edits: `values`, with the rendered parameters' values replaced.
    """
    edited = dict(values)
    for group in _configuration_groups(parameters, values, key_prefix):
        with st.container(border=True):
            columns = st.columns(CONFIGURATION_FORM_COLUMNS)
            position = [0]
            for parameter in group:
                _render_configuration_parameter(
                    parameter, edited, reference, key_prefix, columns, position
                )
    return edited


def _configuration_groups(
    parameters: list[ParameterSpec], values: Mapping[str, str], key_prefix: str
) -> list[list[ParameterSpec]]:
    """Group the top-level parameters into boxes: one for each with active sub-parameters, and
    one for each run of consecutive parameters without, which share a box instead of taking a
    box each."""
    groups: list[list[ParameterSpec]] = []
    previous_was_simple = False
    for parameter in parameters:
        current = st.session_state.get(f"{key_prefix}_{parameter.name}", values[parameter.name])
        simple = not isinstance(parameter, CategoricalParameter) or not active_sub_parameters(
            parameter, {parameter.name: str(current)}
        )
        if simple and previous_was_simple:
            groups[-1].append(parameter)
        else:
            groups.append([parameter])
        previous_was_simple = simple
    return groups


def _render_configuration_parameter(
    parameter: ParameterSpec,
    edited: dict[str, str],
    reference: Mapping[str, str],
    key_prefix: str,
    columns: list,
    position: list[int],
) -> None:
    """Render one parameter's widget in the next free column, then its active sub-parameters."""
    column = columns[position[0] % len(columns)]
    position[0] += 1
    key = f"{key_prefix}_{parameter.name}"
    current = st.session_state.get(key, edited[parameter.name])
    modified = parameter.name not in reference or not same_value(
        str(current), reference[parameter.name]
    )
    label = parameter.name + (MODIFIED_MARK if modified else "")
    with column:
        if isinstance(parameter, RangeParameter):
            edited[parameter.name] = _range_widget(parameter, label, edited[parameter.name], key)
            return
        edited[parameter.name] = _choice_widget(parameter, label, edited[parameter.name], key)
    for child in active_sub_parameters(parameter, {parameter.name: edited[parameter.name]}):
        _render_configuration_parameter(child, edited, reference, key_prefix, columns, position)


def _choice_widget(parameter: CategoricalParameter, label: str, value: str, key: str) -> str:
    allowed = [choice.value for choice in parameter.choices]
    options = allowed if value in allowed else [*allowed, value]
    return st.selectbox(
        label,
        options,
        index=options.index(value),
        format_func=lambda option: (
            option if option in allowed else f"{option} (not in the parameter space)"
        ),
        help=PARAMETER_HELP.get(parameter.name),
        key=key,
    )


def _range_widget(parameter: RangeParameter, label: str, value: str, key: str) -> str:
    try:
        number = float(value)
    except ValueError:
        number = parameter.lower_bound
    lower, upper = min(parameter.lower_bound, number), max(parameter.upper_bound, number)
    help_text = f"{parameter.kind}, from {parameter.lower_bound:g} to {parameter.upper_bound:g}"
    if parameter.name in PARAMETER_HELP:
        help_text = f"{PARAMETER_HELP[parameter.name]} {help_text.capitalize()}."
    if not parameter.lower_bound <= number <= parameter.upper_bound:
        help_text = f"{value} is outside the parameter space ({help_text})"
    if parameter.kind == "integer":
        chosen = st.number_input(
            label,
            min_value=int(lower),
            max_value=int(upper),
            value=int(number),
            step=1,
            help=help_text,
            key=key,
        )
        return str(int(chosen))
    chosen = st.number_input(
        label,
        min_value=float(lower),
        max_value=float(upper),
        value=float(number),
        step=_step(parameter),
        format="%.6g",
        help=help_text,
        key=key,
    )
    return repr(float(f"{chosen:.10g}"))


def _step(parameter: RangeParameter) -> float:
    """A round step of about a hundredth of the range."""
    return float(
        10 ** math.floor(math.log10((parameter.upper_bound - parameter.lower_bound) / 100))
    )
