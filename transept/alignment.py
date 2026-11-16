"""Reads aligned FASTA files and draws them coloured by topology."""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path

from transept.datasets import TRANSMEMBRANE, Protein

GAP = "-"


@dataclass(slots=True, frozen=True)
class AlignedRow:
    """A row of an alignment."""

    id: str
    aligned: str


def read_fasta(path: Path | str) -> list[AlignedRow]:
    """Reads an aligned FASTA file; the identifier is the first word of each header."""
    rows: list[AlignedRow] = []
    identifier, parts = None, []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(">"):
            if identifier is not None:
                rows.append(AlignedRow(identifier, "".join(parts)))
            identifier, parts = line[1:].split()[0] if line[1:].split() else "", []
        elif line:
            parts.append(line)
    if identifier is not None:
        rows.append(AlignedRow(identifier, "".join(parts)))
    return rows


def topology_row(row: AlignedRow, protein: Protein | None) -> str:
    """Returns the topology letter of every column of a row ('-' at gaps, '?' if unknown)."""
    letters, residue = [], 0
    for char in row.aligned:
        if char == GAP:
            letters.append(GAP)
        else:
            known = protein is not None and residue < len(protein.topology)
            letters.append(protein.topology[residue] if known else "?")
            residue += 1
    return "".join(letters)


def helix_gap_runs(row: AlignedRow, protein: Protein | None) -> int:
    """Counts the gap runs placed between two consecutive transmembrane residues."""
    if protein is None:
        return 0
    topology = topology_row(row, protein)
    residues = [(column, letter) for column, letter in enumerate(topology) if letter != GAP]
    broken = 0
    for (left_column, left), (right_column, right) in zip(residues, residues[1:]):
        if right_column > left_column + 1 and left == right == TRANSMEMBRANE:
            broken += 1
    return broken


def consensus(rows: list[AlignedRow], proteins: dict[str, Protein]) -> list[float]:
    """Returns, for every column, the fraction of residues that are transmembrane."""
    length = max((len(row.aligned) for row in rows), default=0)
    residues, transmembrane = [0] * length, [0] * length
    for row in rows:
        for column, letter in enumerate(topology_row(row, proteins.get(row.id))):
            if letter != GAP:
                residues[column] += 1
                transmembrane[column] += letter == TRANSMEMBRANE
    return [tm / count if count else 0.0 for tm, count in zip(transmembrane, residues)]


def helices(
    fractions: list[float], threshold: float = 0.5, min_length: int = 8
) -> list[tuple[int, int]]:
    """Returns the (first, last) columns of the runs where most residues are transmembrane."""
    found, start = [], None
    for column, fraction in enumerate([*fractions, 0.0]):
        if fraction > threshold and start is None:
            start = column
        elif fraction <= threshold and start is not None:
            if column - start >= min_length:
                found.append((start, column - 1))
            start = None
    return found


def helix_breaking_columns(row: AlignedRow, protein: Protein | None) -> set[int]:
    """Returns the gap columns of a row that lie between two consecutive transmembrane residues."""
    if protein is None:
        return set()
    topology = topology_row(row, protein)
    residues = [(column, letter) for column, letter in enumerate(topology) if letter != GAP]
    breaking: set[int] = set()
    for (left_column, left), (right_column, right) in zip(residues, residues[1:]):
        if right_column > left_column + 1 and left == right == TRANSMEMBRANE:
            breaking.update(range(left_column + 1, right_column))
    return breaking


STYLE = """
<style>
.msa { font-family: "JetBrains Mono", Menlo, Consolas, monospace; font-size: 12px;
       line-height: 1.35; overflow-x: auto; white-space: pre; }
.msa .id { color: #5E5266; display: inline-block; min-width: 12ch; }
.msa .tm { background: #F6E2D8; }
.msa .gap { color: #7A6E80; }
.msa .break { color: #fff; background: #C21F3A; }
.msa .track { color: #A9432A; }
.msa .changed { background: #fdd0a2; }
.msa .same { background: #a1d99b; }
.msa .partly { background: #fee391; }
.msa .different { background: #fc9272; }
.msa .ruler { color: #7A6E80; }
.msa .s0 { background: #F3ECE5; } .msa .s1 { background: #F1D3C3; }
.msa .s2 { background: #E3A98C; } .msa .s3 { color: #fff; background: #A9432A; }
.msa .p0 { background: #FF7D45; } .msa .p1 { background: #FFDB13; }
.msa .p2 { background: #65CBF3; } .msa .p3 { color: #fff; background: #0053D6; }
</style>
"""


@dataclass(slots=True, frozen=True)
class Track:
    """A row of coloured cells drawn above an alignment, one per column.

    Attributes:
        label: Its name, in the place of a protein name.
        values: A value per column, or NaN where it has none.
        scale: "fraction" for values in [0, 1] (four shades of terracotta, darker is higher), or
            "plddt" for AlphaFold's pLDDT in [0, 100], with AlphaFold's own colours.
    """

    label: str
    values: object
    scale: str = "fraction"


def shade(value: float, scale: str = "fraction") -> str:
    """The CSS class of a value on a scale, or "" for NaN."""
    if value != value:
        return ""
    if scale == "plddt":
        return "p3" if value > 90 else "p2" if value > 70 else "p1" if value > 50 else "p0"
    return "s3" if value >= 0.75 else "s2" if value >= 0.5 else "s1" if value >= 0.25 else "s0"


def _track_cell(value: float, scale: str) -> str:
    kind = shade(value, scale)
    return f'<span class="{kind}"> </span>' if kind else " "


def _agreement_cell(value: float) -> str:
    if value != value:  # NaN: fewer than two residues in the column
        return " "
    kind = "same" if value >= 0.9 else "partly" if value >= 0.5 else "different"
    return f'<span class="{kind}"> </span>'


def _cell(char: str, letter: str, breaking: bool, changed: bool, value_shade: str | None) -> str:
    """One residue or gap of a row, with the class that colours it."""
    escaped = html.escape(char)
    if breaking:
        css = "break"
    elif changed:
        css = "changed"
    elif char == GAP:
        css = "gap"
    elif value_shade is not None:
        css = value_shade
    elif letter == TRANSMEMBRANE:
        css = "tm"
    else:
        css = ""
    return f'<span class="{css}">{escaped}</span>' if css else escaped


def _row_line(
    row_number: int,
    row: AlignedRow,
    protein: Protein | None,
    columns: range,
    label: str,
    changed: set[tuple[int, int]] | None,
    colour: tuple[object, str] | None,
) -> str:
    topology = topology_row(row, protein)
    breaking = helix_breaking_columns(row, protein)
    cells = []
    for column in columns:
        char = row.aligned[column] if column < len(row.aligned) else " "
        letter = topology[column] if column < len(topology) else " "
        value_shade = None
        if colour is not None:
            values, scale = colour
            value_shade = shade(float(values[row_number][column]), scale)
        cells.append(
            _cell(
                char,
                letter,
                column in breaking,
                bool(changed) and (row_number, column) in changed,
                value_shade,
            )
        )
    return f'<span class="id">{label}</span>{"".join(cells)}'


def _track_lines(
    start: int,
    end: int,
    label_width: int,
    agreement: list[float] | None,
    tracks: list[Track] | None,
    consensus_line: str | None,
) -> list[str]:
    """The optional rows above the proteins: agreement, tracks and consensus."""
    lines = []
    if agreement is not None:
        cells = "".join(
            _agreement_cell(agreement[column]) for column in range(start, min(end, len(agreement)))
        )
        lines.append(
            f'<span class="id">{html.escape("Agreement".ljust(label_width))}</span>{cells}'
        )
    for track in tracks or []:
        values = track.values
        cells = "".join(
            _track_cell(float(values[column]), track.scale)
            for column in range(start, min(end, len(values)))
        )
        lines.append(
            f'<span class="id">{html.escape(track.label.ljust(label_width))}</span>{cells}'
        )
    if consensus_line is not None:
        label = html.escape("Consensus".ljust(label_width))
        lines.append(
            f'<span class="track"><span class="id">{label}</span>'
            f"{html.escape(consensus_line[start:end])}</span>"
        )
    return lines


def render_html(
    rows: list[AlignedRow],
    proteins: dict[str, Protein],
    start: int,
    width: int,
    agreement: list[float] | None = None,
    changed: set[tuple[int, int]] | None = None,
    tracks: list[Track] | None = None,
    consensus_line: str | None = None,
    colour: tuple[object, str] | None = None,
) -> str:
    """Draws columns [start, start + width) of an alignment; transmembrane residues are shaded.

    Args:
        agreement: Optional fraction of the residue pairs of every column found in another
            alignment; drawn as a coloured track (green >= 0.9, yellow >= 0.5, red below).
        changed: Optional (row, column) cells whose residue lost most of its partners; shaded.
        tracks: Optional rows of coloured cells, one per column, drawn above the proteins.
        consensus_line: Optional consensus residue of every column, drawn above the proteins.
        colour: Optional (values per cell as an (N, L) matrix, scale): colours every residue by
            its value instead of shading the transmembrane ones. Gaps that break a helix stay red.
    """
    end = min(start + width, max((len(row.aligned) for row in rows), default=0))
    label_width = max((len(row.id) for row in rows), default=4) + 2
    ruler = "".join(
        str(column + 1).ljust(10)[:10] if (column - start) % 10 == 0 else ""
        for column in range(start, end)
    )
    lines = [f'<span class="ruler">{"".ljust(label_width)}{html.escape(ruler)}</span>']
    fractions = consensus(rows, proteins)
    track = "".join(
        "M" if fractions[column] > 0.5 else "·" for column in range(start, min(end, len(fractions)))
    )
    label = html.escape("TM consensus".ljust(label_width))
    lines.append(f'<span class="track"><span class="id">{label}</span>{track}</span>')
    lines += _track_lines(start, end, label_width, agreement, tracks, consensus_line)
    for row_number, row in enumerate(rows):
        lines.append(
            _row_line(
                row_number,
                row,
                proteins.get(row.id),
                range(start, end),
                html.escape(row.id.ljust(label_width)),
                changed,
                colour,
            )
        )
    return STYLE + '<div class="msa">' + "\n".join(lines) + "</div>"
