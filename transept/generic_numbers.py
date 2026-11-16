"""GPCRdb generic residue numbers on an alignment, without Streamlit.

GPCRdb gives every residue of a G protein-coupled receptor a generic number, such as 3.50x50: the
helix (3), the position relative to the most conserved residue of that helix in the class (50),
and a structure-based correction after the x. Residues with the same generic number play the same
role in different receptors, so a good alignment puts them in the same column. The numbers come
from the GPCRdb web service (https://gpcrdb.org/services/), asked for once per receptor and kept
under TRANSEPT_HOME, and only when the user asks: Transept never goes on the network on its own.

Each receptor is looked up by its identifier, which in the GPCR benchmark is its GPCRdb entry name
(e.g. adrb2_human). Proteins that GPCRdb does not know are left without numbers.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from transept import settings, superposition
from transept.alignment import AlignedRow
from transept.analysis import residue_index
from transept.datasets import Protein

SERVICE = "https://gpcrdb.org/services/residues/extended/{entry}/"
TIMEOUT_SECONDS = 30
CACHE = "gpcrdb"
# Positions of well-known motifs, as numbers of the scheme of the class (before the x). The names
# are those of class A; in other classes the same positions hold other residues.
MOTIFS = (
    ("D/E-R-Y (3.49–3.51)", ("3.49", "3.50", "3.51")),
    ("C-W-x-P (6.47–6.50)", ("6.47", "6.48", "6.49", "6.50")),
    ("N-P-x-x-Y (7.49–7.53)", ("7.49", "7.50", "7.51", "7.52", "7.53")),
    ("P-I-F (3.40, 5.50, 6.44)", ("3.40", "5.50", "6.44")),
)


def cache_directory() -> Path:
    return settings.transept_home() / CACHE


def cached(entry: str) -> list[dict] | None:
    """The residues of a receptor kept from an earlier request, if any."""
    path = cache_directory() / f"{entry}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(entry: str) -> list[dict] | None:
    """The residues of a receptor from GPCRdb, kept for later; None if GPCRdb does not know it or
    cannot be reached."""
    found = cached(entry)
    if found is not None:
        return found
    request = urllib.request.Request(
        SERVICE.format(entry=entry), headers={"User-Agent": "Transept (local application)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None
    if not isinstance(data, list) or not data:
        return None
    directory = cache_directory()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{entry}.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_all(
    entries: list[str], progress: Callable[[int, int], None] | None = None, workers: int = 4
) -> dict[str, list[dict] | None]:
    """The residues of several receptors, asked for a few at a time; progress(done, total) is
    called after each one."""
    found: dict[str, list[dict] | None] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for done, (entry, residues) in enumerate(zip(entries, pool.map(fetch, entries)), start=1):
            found[entry] = residues
            if progress is not None:
                progress(done, len(entries))
    return found


def scheme_label(generic: str) -> str:
    """The number of the scheme of the class, e.g. "3.50" for "3.50x50"."""
    return generic.split("x", 1)[0]


def numbering(
    rows: list[AlignedRow], proteins: dict[str, Protein], residues: dict[str, list[dict]]
) -> np.ndarray:
    """The generic number of every cell (protein, column), or "" where there is none.

    A residue of the sequence is matched to GPCRdb by its position when the amino acids agree,
    and else by a sequence alignment, as the structures of the 3D view.
    """
    index = residue_index(rows)
    numbers = np.full(index.shape, "", dtype=object)
    for number, row in enumerate(rows):
        protein = proteins.get(row.id)
        known = residues.get(row.id)
        if protein is None or not known:
            continue
        letters = {int(r["sequence_number"]): r["amino_acid"] for r in known}
        generic = {
            int(r["sequence_number"]): r["display_generic_number"]
            for r in known
            if r.get("display_generic_number")
        }
        mapped = superposition.map_residues(protein.residues, letters)
        for column in np.nonzero(index[number] >= 0)[0]:
            position = mapped.get(int(index[number, column]))
            if position in generic:
                numbers[number, column] = generic[position]
    return numbers


def cells_by_number(numbers: np.ndarray) -> dict[str, list[tuple[int, int]]]:
    """The cells (protein, column) of every generic number, found in one pass."""
    cells: dict[str, list[tuple[int, int]]] = {}
    for (row, column), value in np.ndenumerate(numbers):
        if value:
            cells.setdefault(value, []).append((row, column))
    return cells


@dataclass(slots=True, frozen=True)
class Position:
    """Where the residues of a generic number are in an alignment.

    Attributes:
        generic: The generic number, e.g. 3.50x50.
        column: The column holding most of them (0-based).
        aligned: How many receptors have it in that column.
        receptors: How many receptors have a residue with that number.
        residues: The residue of every receptor with that number, in the order of the rows, or "-".
    """

    generic: str
    column: int
    aligned: int
    receptors: int
    residues: str


def position(
    cells: dict[str, list[tuple[int, int]]], rows: list[AlignedRow], generic: str
) -> Position | None:
    """Where a generic number falls in the alignment; None if no receptor has it."""
    found = cells.get(generic)
    if not found:
        return None
    column, aligned = Counter(column for _, column in found).most_common(1)[0]
    letters = ["-"] * len(rows)
    for row, cell in found:
        letters[row] = rows[row].aligned[cell]
    return Position(generic, column, aligned, len(found), "".join(letters))


def by_scheme(cells: dict[str, list[tuple[int, int]]], label: str) -> str | None:
    """The full generic number with a given number of the scheme of the class (e.g. 3.50)."""
    return next((generic for generic in cells if scheme_label(generic) == label), None)


def reference_positions(
    cells: dict[str, list[tuple[int, int]]], rows: list[AlignedRow]
) -> list[Position]:
    """The x.50 position of every helix: the most conserved residue of each helix in the class."""
    found = []
    for helix in range(1, 8):
        generic = by_scheme(cells, f"{helix}.50")
        located = position(cells, rows, generic) if generic else None
        if located is not None:
            found.append(located)
    return found


def is_helix_number(generic: str) -> bool:
    """Whether a generic number belongs to one of the seven helices (1.xx to 7.xx), not a loop."""
    return len(generic) > 1 and generic[0] in "1234567" and generic[1] == "."


def consistency(cells: dict[str, list[tuple[int, int]]], rows: list[AlignedRow]) -> tuple[int, int]:
    """Over every generic number of the helices, how many of its residues are in the column of
    most of them, and how many residues have such a number."""
    aligned = total = 0
    for generic in cells:
        if is_helix_number(generic):
            located = position(cells, rows, generic)
            aligned += located.aligned
            total += located.receptors
    return aligned, total


def helix_consistency(
    cells: dict[str, list[tuple[int, int]]], rows: list[AlignedRow]
) -> dict[int, float]:
    """For every helix, the fraction of its numbered residues that are in the column of most
    residues with the same number."""
    aligned: Counter = Counter()
    total: Counter = Counter()
    for generic in cells:
        if is_helix_number(generic):
            located = position(cells, rows, generic)
            helix = int(generic[0])
            aligned[helix] += located.aligned
            total[helix] += located.receptors
    return {helix: aligned[helix] / total[helix] for helix in sorted(total) if total[helix]}


def motif_rows(cells: dict[str, list[tuple[int, int]]], rows: list[AlignedRow]) -> list[dict]:
    """For every motif, its consensus and whether each of its positions is in one column."""
    table = []
    for name, labels in MOTIFS:
        located = [
            position(cells, rows, generic)
            for generic in (by_scheme(cells, label) for label in labels)
            if generic
        ]
        located = [item for item in located if item is not None]
        if not located:
            continue
        consensus = "".join(
            Counter(letter for letter in item.residues if letter != "-").most_common(1)[0][0]
            for item in located
        )
        in_one_column = sum(item.aligned == item.receptors for item in located)
        table.append(
            {
                "motif": name,
                "consensus": consensus,
                "positions in one column": f"{in_one_column} of {len(located)}",
                "receptors": max(item.receptors for item in located),
                "columns": ", ".join(str(item.column + 1) for item in located),
            }
        )
    return table


def x50_line(cells: dict[str, list[tuple[int, int]]], rows: list[AlignedRow], length: int) -> str:
    """A line with the helix number at the column of its x.50 position, and "·" elsewhere."""
    line = ["·"] * length
    for item in reference_positions(cells, rows):
        line[item.column] = item.generic[0]
    return "".join(line)
