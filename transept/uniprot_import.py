"""Proteins from UniProt and AlphaFold DB, ready to become a dataset, without Streamlit.

From a list of UniProt accessions or entry names (P29972 or AQP1_HUMAN), it gets every protein's
sequence and its topology from UniProt (https://rest.uniprot.org), and its structure model from
AlphaFold DB (https://alphafold.ebi.ac.uk). Only the identifiers are sent, only when the user asks,
and the answers are kept under TRANSEPT_HOME, so nothing is asked twice.

The topology comes from the features of the UniProt entry: `Transmembrane` and `Intramembrane`
(re-entrant half-helices, such as those of aquaporins) are marked as transmembrane (M), so the
search never opens a gap inside them; `Topological domain` gives the cytoplasmic (I) and the other
(O) sides.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from transept import settings
from transept.dataset_builder import Source

SEARCH = "https://rest.uniprot.org/uniprotkb/search?{query}"
FIELDS = "accession,id,protein_name,organism_name,sequence,ft_transmem,ft_intramem,ft_topo_dom"
ALPHAFOLD = "https://alphafold.ebi.ac.uk/api/prediction/{accession}"
TIMEOUT_SECONDS = 30
USER_AGENT = "Transept (local application)"
CACHE = "downloads"
IDENTIFIER = re.compile(r"[A-Za-z0-9_]+")
MEMBRANE_FEATURES = ("Transmembrane", "Intramembrane")
CYTOPLASMIC = "Cytoplasmic"


@dataclass(slots=True, frozen=True)
class Entry:
    """A protein as UniProt describes it.

    Attributes:
        accession: Its UniProt accession, e.g. P29972.
        name: Its identifier in the dataset: the UniProt entry name in lower case, e.g. aqp1_human.
        description: Its protein name and organism, for the user.
        sequence: Its canonical sequence.
        topology: One letter per residue: M transmembrane, I cytoplasmic, O any other.
        helices: How many transmembrane and intramembrane segments it has.
    """

    accession: str
    name: str
    description: str
    sequence: str
    topology: str
    helices: int


@dataclass(slots=True, frozen=True)
class Imported:
    """What was found for a list of identifiers.

    Attributes:
        entries: The proteins found, in the order given.
        models: The path of the AlphaFold model of every protein that has one, by name.
        problems: What could not be used, one sentence each.
    """

    entries: tuple[Entry, ...]
    models: dict[str, Path]
    problems: tuple[str, ...]


def parse_identifiers(text: str) -> list[str]:
    """The identifiers in a text, separated by spaces, commas or lines, without repetitions."""
    found = []
    for token in re.split(r"[\s,;]+", text.strip()):
        if token and token.upper() not in (item.upper() for item in found):
            found.append(token)
    return found


def cache_directory() -> Path:
    return settings.transept_home() / CACHE


def _get(url: str) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def _cached(kind: str, key: str, suffix: str, fetch: Callable[[], bytes | None]) -> bytes | None:
    path = cache_directory() / kind / f"{key}{suffix}"
    if path.is_file():
        return path.read_bytes()
    data = fetch()
    if data:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


def uniprot_record(identifier: str) -> dict | None:
    """The UniProt record of an accession or entry name; None if UniProt does not know it."""
    if not IDENTIFIER.fullmatch(identifier):
        return None
    key = identifier.upper()
    # Entry names have an underscore (AQP1_HUMAN), accessions do not (P29972).
    field = "id" if "_" in key else "accession"
    query = urllib.parse.urlencode(
        {"query": f"{field}:{key}", "fields": FIELDS, "format": "json", "size": 1}
    )
    data = _cached("uniprot", key, ".json", lambda: _get(SEARCH.format(query=query)))
    if not data:
        return None
    results = json.loads(data).get("results") or []
    return results[0] if results else None


def topology_of(record: dict) -> tuple[str, int]:
    """The topology string of a UniProt record, and how many membrane segments it has."""
    length = record["sequence"]["length"]
    letters = ["O"] * length
    segments = 0
    for feature in record.get("features", []):
        location = feature.get("location", {})
        start = location.get("start", {}).get("value")
        end = location.get("end", {}).get("value")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if feature["type"] in MEMBRANE_FEATURES:
            letter = "M"
            segments += 1
        elif feature["type"] == "Topological domain" and CYTOPLASMIC in feature.get(
            "description", ""
        ):
            letter = "I"
        else:
            continue
        for position in range(max(start, 1) - 1, min(end, length)):
            if letters[position] != "M":
                letters[position] = letter
    return "".join(letters), segments


def entry_of(record: dict) -> Entry:
    topology, segments = topology_of(record)
    names = record.get("proteinDescription", {}).get("recommendedName", {})
    protein = names.get("fullName", {}).get("value", "")
    organism = record.get("organism", {}).get("scientificName", "")
    return Entry(
        accession=record["primaryAccession"],
        name=record["uniProtkbId"].lower(),
        description=", ".join(part for part in (protein, organism) if part),
        sequence=record["sequence"]["value"],
        topology=topology,
        helices=segments,
    )


def alphafold_model(entry: Entry) -> tuple[bytes | None, str | None]:
    """The AlphaFold model of a protein, if it covers its whole UniProt sequence.

    Returns:
        The model and None, or None and why there is no usable model.
    """
    data = _cached(
        "alphafold",
        entry.accession,
        ".json",
        lambda: _get(ALPHAFOLD.format(accession=entry.accession)),
    )
    predictions = json.loads(data) if data else []
    if not predictions:
        return None, f"{entry.name}: AlphaFold DB has no model of {entry.accession}"
    prediction = predictions[0]
    if prediction.get("uniprotSequence", prediction.get("sequence")) != entry.sequence:
        return None, (
            f"{entry.name}: the AlphaFold model of {entry.accession} is not of the current UniProt "
            "sequence (it may be split into fragments, as for proteins longer than 2,700 residues)"
        )
    model = _cached("alphafold", entry.accession, ".pdb", lambda: _get(prediction["pdbUrl"]))
    if not model:
        return (
            None,
            f"{entry.name}: the AlphaFold model of {entry.accession} could not be downloaded",
        )
    return model, None


def _one(identifier: str) -> tuple[Entry | None, bytes | None, str | None]:
    record = uniprot_record(identifier)
    if record is None:
        return None, None, f"{identifier}: not found in UniProt (or UniProt could not be reached)"
    entry = entry_of(record)
    model, problem = alphafold_model(entry)
    if entry.helices == 0:
        problem = (problem + "; " if problem else "") + (
            f"{entry.name}: UniProt has no transmembrane segment for it; give its topology in a "
            "three-line file instead"
        )
    return entry, model, problem


def fetch(
    identifiers: list[str],
    progress: Callable[[int, int], None] | None = None,
    workers: int = 4,
) -> Imported:
    """Gets the proteins, a few at a time; progress(done, total) is called after each one."""
    entries, models, problems = [], {}, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = pool.map(_one, identifiers)
        for done, (entry, model, problem) in enumerate(results, start=1):
            if problem:
                problems.append(problem)
            if entry is not None and entry.helices > 0:
                if any(item.name == entry.name for item in entries):
                    problems.append(f"{entry.name}: given twice")
                else:
                    entries.append(entry)
                    if model is not None:
                        path = cache_directory() / "alphafold" / f"{entry.accession}.pdb"
                        models[entry.name] = path
            if progress is not None:
                progress(done, len(identifiers))
    return Imported(tuple(entries), models, tuple(problems))


def three_line(entries: tuple[Entry, ...]) -> str:
    """The three-line topology file of some proteins."""
    return "".join(
        f">{entry.name} | {entry.accession}\n{entry.sequence}\n{entry.topology}\n"
        for entry in entries
    )


def sources(imported: Imported) -> tuple[Source, tuple[Source, ...]]:
    """The topology file and the structure models, named as a dataset needs them."""
    topology = Source("topology.3line", data=three_line(imported.entries).encode("utf-8"))
    models = tuple(
        Source(f"{name}.pdb", path=path) for name, path in sorted(imported.models.items())
    )
    return topology, models
