"""An alignment with its structures superposed, ready to open in ChimeraX or PyMOL.

The structure models are moved onto the first one according to the alignment (see
superposition), so that the residues of a column lie close in space when the column is right. The
package also holds the alignment, so that ChimeraX can link its columns to the residues, and the
transmembrane segments, which the scripts colour.
"""

from __future__ import annotations

from pathlib import Path

from transept import exports, superposition
from transept.alignment import AlignedRow
from transept.datasets import Protein

PALETTE = ("#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#76b7b2", "#edc948", "#ff9da7", "#9c755f")
OTHER_COLOUR = "#d9d9d9"
# The same colours by CSS name: in ChimeraX, "#..." could be read as a model.
NAMES = (
    "steelblue", "darkorange", "forestgreen", "orchid", "cadetblue", "gold", "lightpink", "sienna"
)  # fmt: skip
OTHER_NAME = "lightgray"
STRUCTURES = "structures"
README = """Alignment {stem}, with the structure models superposed according to it.

Open it in:
- ChimeraX: open open_in_chimerax.cxc (File > Open, or "open path/open_in_chimerax.cxc").
  The alignment opens in a sequence viewer linked to the structures: selecting a column
  selects its residues in 3D.
- PyMOL: File > Run Script... and choose open_in_pymol.py (or "run path/open_in_pymol.py").
- Jalview: open alignment.fasta, then File > Load Features / Annotations with tm_features.txt
  to see the transmembrane helices; the structures can be linked from structures/.

If ChimeraX does not find the files, run "cd path/to/this/folder" first.

The transmembrane residues of each protein have its own colour; the rest is light grey.
The first protein is the reference: the others are moved onto it with their aligned
transmembrane residues (Kabsch superposition). If the columns are right, those residues
coincide; a large RMSD means the alignment places them apart, or the proteins differ.

protein  aligned TM pairs with the reference  RMSD (A)
{table}
{left_out}"""


def _ranges(numbers: list[int]) -> list[tuple[int, int]]:
    """Groups sorted residue numbers into consecutive ranges."""
    ranges: list[tuple[int, int]] = []
    for number in numbers:
        if ranges and number == ranges[-1][1] + 1:
            ranges[-1] = (ranges[-1][0], number)
        else:
            ranges.append((number, number))
    return ranges


def _transmembrane_residues(item: superposition.PlacedStructure) -> list[int]:
    structure = item.structure
    return sorted(structure.columns[column] for column in structure.transmembrane)


def chimerax_script(placed: list[superposition.PlacedStructure]) -> str:
    """Writes a ChimeraX command script that opens and colours the structures and the alignment."""
    lines = ["# Written by Transept"]
    lines += [f"open {STRUCTURES}/{item.structure.id}.pdb" for item in placed]
    lines += ["open alignment.fasta", "hide atoms", "show cartoons", f"color {OTHER_NAME} target c"]
    for model, item in enumerate(placed, start=1):
        residues = _transmembrane_residues(item)
        if residues:
            spec = ",".join(f"{a}-{b}" if a != b else f"{a}" for a, b in _ranges(residues))
            lines.append(f"color #{model}:{spec} {NAMES[(model - 1) % len(NAMES)]} target c")
    lines.append("view")
    return "\n".join(lines) + "\n"


def pymol_script(placed: list[superposition.PlacedStructure]) -> str:
    """Writes a PyMOL Python script that opens and colours the structures."""
    lines = [
        "# Written by Transept. Run it with File > Run Script..., or: run open_in_pymol.py",
        "import os",
        "from pymol import cmd",
        "",
        "here = os.path.dirname(os.path.abspath(globals().get('__script__')",
        "                       or globals().get('__file__') or 'open_in_pymol.py'))",
        "",
    ]
    for index, colour in enumerate(PALETTE):
        rgb = [round(int(colour[i : i + 2], 16) / 255, 3) for i in (1, 3, 5)]
        lines.append(f"cmd.set_color('transept_{index}', {rgb})")
    grey = round(int(OTHER_COLOUR[1:3], 16) / 255, 3)
    lines.append(f"cmd.set_color('transept_other', {[grey] * 3})")
    for index, item in enumerate(placed):
        name = item.structure.id
        lines.append(f"cmd.load(os.path.join(here, '{STRUCTURES}', '{name}.pdb'), '{name}')")
    lines += ["cmd.hide('everything')", "cmd.show('cartoon')", "cmd.color('transept_other')"]
    for index, item in enumerate(placed):
        residues = _transmembrane_residues(item)
        if residues:
            spec = "+".join(f"{a}-{b}" if a != b else f"{a}" for a, b in _ranges(residues))
            colour = f"transept_{index % len(PALETTE)}"
            lines.append(f"cmd.color('{colour}', '{item.structure.id} and resi {spec}')")
    lines.append("cmd.orient()")
    return "\n".join(lines) + "\n"


def files(
    rows: list[AlignedRow], proteins: dict[str, Protein], models: dict[str, Path], stem: str
) -> dict[str, str]:
    """Returns the files of the package, by name.

    Args:
        rows: The alignment.
        proteins: The sequence and topology of each protein.
        models: The structure model of each protein that has one.
        stem: A name for the alignment, for the README.
    """
    structures = [
        superposition.read_structure(row, proteins[row.id], models[row.id])
        for row in rows
        if row.id in proteins and row.id in models
    ]
    placed, left_out = superposition.superpose(structures)
    package = {f"{STRUCTURES}/{item.structure.id}.pdb": item.moved_pdb() + "\n" for item in placed}
    package["alignment.fasta"] = exports.to_fasta(rows)
    package["alignment.sto"] = exports.to_stockholm(rows, proteins)
    package["tm_features.txt"] = exports.jalview_features(proteins)
    package["open_in_chimerax.cxc"] = chimerax_script(placed)
    package["open_in_pymol.py"] = pymol_script(placed)
    width = max((len(item.structure.id) for item in placed), default=7) + 2
    table = "\n".join(
        f"{item.structure.id.ljust(width)} {'reference' if index == 0 else item.pairs:>9}"
        f"  {'' if index == 0 else f'{item.rmsd:.2f}'}"
        for index, item in enumerate(placed)
    )
    without = [row.id for row in rows if row.id not in models]
    notes = []
    if left_out:
        notes.append(
            "Left out, with too few aligned transmembrane residues in common with the "
            f"reference: {', '.join(left_out)}."
        )
    if without:
        notes.append(f"Without a structure model: {', '.join(without)}.")
    package["README.txt"] = README.format(
        stem=stem, table=table, left_out="\n".join(notes) + ("\n" if notes else "")
    )
    return package
