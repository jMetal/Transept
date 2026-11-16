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
.msa .id { color: #4A5A68; display: inline-block; min-width: 12ch; }
.msa .tm { background: #D7ECEF; }
.msa .gap { color: #8A98A4; }
.msa .break { color: #fff; background: #B42318; }
.msa .track { color: #1F7A8C; }
.msa .changed { background: #fdd0a2; }
.msa .same { background: #a1d99b; }
.msa .partly { background: #fee391; }
.msa .different { background: #fc9272; }
.msa .ruler { color: #8A98A4; }
</style>
"""


def _agreement_cell(value: float) -> str:
    if value != value:  # NaN: fewer than two residues in the column
        return " "
    kind = "same" if value >= 0.9 else "partly" if value >= 0.5 else "different"
    return f'<span class="{kind}"> </span>'


def render_html(
    rows: list[AlignedRow],
    proteins: dict[str, Protein],
    start: int,
    width: int,
    agreement: list[float] | None = None,
    changed: set[tuple[int, int]] | None = None,
) -> str:
    """Draws columns [start, start + width) of an alignment; transmembrane residues are shaded.

    Args:
        agreement: Optional fraction of the residue pairs of every column found in another
            alignment; drawn as a coloured track (green >= 0.9, yellow >= 0.5, red below).
        changed: Optional (row, column) cells whose residue lost most of its partners; shaded.
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
    if agreement is not None:
        cells = "".join(
            _agreement_cell(agreement[column]) for column in range(start, min(end, len(agreement)))
        )
        label = html.escape("Agreement".ljust(label_width))
        lines.append(f'<span class="id">{label}</span>{cells}')
    for row_number, row in enumerate(rows):
        protein = proteins.get(row.id)
        topology = topology_row(row, protein)
        breaking = helix_breaking_columns(row, protein)
        cells = []
        for column in range(start, end):
            char = row.aligned[column] if column < len(row.aligned) else " "
            letter = topology[column] if column < len(topology) else " "
            escaped = html.escape(char)
            if column in breaking:
                cells.append(f'<span class="break">{escaped}</span>')
            elif changed and (row_number, column) in changed:
                cells.append(f'<span class="changed">{escaped}</span>')
            elif char == GAP:
                cells.append(f'<span class="gap">{escaped}</span>')
            elif letter == TRANSMEMBRANE:
                cells.append(f'<span class="tm">{escaped}</span>')
            else:
                cells.append(escaped)
        label = html.escape(row.id.ljust(label_width))
        lines.append(f'<span class="id">{label}</span>{"".join(cells)}')
    return STYLE + '<div class="msa">' + "\n".join(lines) + "</div>"
