"""Alignments in other formats: Clustal, Stockholm with topology, and Jalview features."""

from __future__ import annotations

import io
import zipfile

from transept.alignment import GAP, AlignedRow, topology_row
from transept.datasets import TRANSMEMBRANE, Protein

BLOCK = 60
TM_FEATURE = "Transmembrane"
TM_COLOUR = "c6dbef"


def to_fasta(rows: list[AlignedRow]) -> str:
    """Writes an aligned FASTA file, 60 columns per line."""
    lines = []
    for row in rows:
        lines.append(f">{row.id}")
        lines += [row.aligned[i : i + BLOCK] for i in range(0, len(row.aligned), BLOCK)]
    return "\n".join(lines) + "\n"


def to_clustal(rows: list[AlignedRow]) -> str:
    """Writes a Clustal file, 60 columns per block."""
    width = max((len(row.id) for row in rows), default=0) + 4
    length = max((len(row.aligned) for row in rows), default=0)
    lines = ["CLUSTAL multiple sequence alignment (Transept)", ""]
    for start in range(0, length, BLOCK):
        lines += [row.id.ljust(width) + row.aligned[start : start + BLOCK] for row in rows]
        lines.append("")
    return "\n".join(lines) + "\n"


def to_stockholm(rows: list[AlignedRow], proteins: dict[str, Protein]) -> str:
    """Writes a Stockholm file with the topology of every residue as a `#=GR <id> TM` line.

    Gaps are '.' in the annotation; residues carry their topology letter (M, I, O, S...).
    """
    width = max((len(row.id) for row in rows), default=0) + 10
    lines = ["# STOCKHOLM 1.0", "#=GF DE Alignment found by Transept"]
    for row in rows:
        lines.append(row.id.ljust(width) + row.aligned)
        if row.id in proteins:
            annotation = topology_row(row, proteins[row.id]).replace(GAP, ".")
            lines.append(f"#=GR {row.id} TM".ljust(width) + annotation)
    lines.append("//")
    return "\n".join(lines) + "\n"


def jalview_features(proteins: dict[str, Protein]) -> str:
    """Writes a Jalview features file with the transmembrane segments of every protein."""
    lines = [f"{TM_FEATURE}\t{TM_COLOUR}", "STARTGROUP\ttopology"]
    for protein in proteins.values():
        start = None
        for position, letter in enumerate([*protein.topology, ""]):
            if letter == TRANSMEMBRANE and start is None:
                start = position
            elif letter != TRANSMEMBRANE and start is not None:
                lines.append(
                    f"Transmembrane helix\t{protein.id}\t-1\t{start + 1}\t{position}\t{TM_FEATURE}"
                )
                start = None
    lines.append("ENDGROUP\ttopology")
    return "\n".join(lines) + "\n"


def bundle(files: dict[str, str | bytes]) -> bytes:
    """Packs files into a zip archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()
