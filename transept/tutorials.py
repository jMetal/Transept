"""The tutorials of `docs/tutorials/`, so that they can be read inside Transept."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path

from transept import settings

REPOSITORY_URL = "https://github.com/jMetal/Transept/blob/main"
DIRECTORY = "docs/tutorials"
OVERVIEW = "overview"
ADD_YOUR_OWN_PROTEINS = "add-your-own-proteins"
OPERATORS = "operators"
RELIABILITY = "is-my-alignment-reliable"
WHY_SEVERAL_OBJECTIVES = "why-several-objectives"
WHAT_TRANSEPT_OPTIMISES = "what-transept-optimises"
CHOOSE_AN_ALGORITHM = "choose-an-algorithm"
# The order in which the tutorials are meant to be read; the others follow, by file name.
READING_ORDER = (
    OVERVIEW,
    ADD_YOUR_OWN_PROTEINS,
    WHY_SEVERAL_OBJECTIVES,
    WHAT_TRANSEPT_OPTIMISES,
    RELIABILITY,
    CHOOSE_AN_ALGORITHM,
    OPERATORS,
)
# A relative link, but not an image: images are shown from the disk (see `parts`).
RELATIVE_LINK = re.compile(r"(?<!!)(\[[^\]]*)\]\((?![a-zA-Z][a-zA-Z0-9+.-]*:|#)([^)\s]+)\)")
# An image on a line of its own: ![caption](images/file.png).
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)\s]+)\)[ \t]*$", re.MULTILINE)


@dataclass(slots=True, frozen=True)
class Tutorial:
    """A tutorial.

    Attributes:
        name: The name of its file, without the extension.
        title: Its first heading.
        text: Its Markdown, with links that also work outside the repository.
        directory: The folder of its file, where its images are.
    """

    name: str
    title: str
    text: str
    directory: Path | None = None


@dataclass(slots=True, frozen=True)
class Figure:
    """An image of a tutorial, with the path of its file and its caption."""

    path: Path
    caption: str


def parts(tutorial: Tutorial) -> list[str | Figure]:
    """The text of a tutorial split at its images, which Streamlit's Markdown does not load from
    the disk: text and figures, in order. An image whose file is missing stays as text."""
    found: list[str | Figure] = []
    start = 0
    for match in IMAGE.finditer(tutorial.text):
        path = (tutorial.directory or Path()) / match.group(2)
        if tutorial.directory is None or not path.is_file():
            continue
        found.append(tutorial.text[start : match.start()])
        found.append(Figure(path, match.group(1)))
        start = match.end()
    found.append(tutorial.text[start:])
    return [part for part in found if not isinstance(part, str) or part.strip()]


def absolute_links(text: str) -> str:
    """Points the relative links of a tutorial to the repository, which Transept does not serve."""

    def to_repository(match: re.Match) -> str:
        target = posixpath.normpath(posixpath.join(DIRECTORY, match.group(2)))
        return f"{match.group(1)}]({REPOSITORY_URL}/{target})"

    return RELATIVE_LINK.sub(to_repository, text)


def read_tutorial(path: Path) -> Tutorial:
    """Reads a tutorial; its title is its first heading, or else the name of the file."""
    text = path.read_text(encoding="utf-8")
    title = next(
        (line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem
    )
    return Tutorial(path.stem, title, absolute_links(text), path.parent)


def reading_position(name: str) -> tuple[int, str]:
    """Where a tutorial goes in Learn: by READING_ORDER, and then by name."""
    order = READING_ORDER.index(name) if name in READING_ORDER else len(READING_ORDER)
    return order, name


def list_tutorials(directory: Path | None = None) -> list[Tutorial]:
    """Returns the tutorials that are written, in the order in which they are meant to be read."""
    folder = directory or settings.REPOSITORY / DIRECTORY
    paths = sorted(folder.glob("*.md"), key=lambda path: reading_position(path.stem))
    return [read_tutorial(path) for path in paths]


@dataclass(slots=True, frozen=True)
class Planned:
    """A tutorial that is not written yet, shown in Learn as coming soon.

    Attributes:
        name: The name its file will have, without the extension.
        title: Its title.
        summary: What it is for, in a sentence or two.
        contents: What it will cover, one item each.
    """

    name: str
    title: str
    summary: str
    contents: tuple[str, ...]


PLANNED = (
    Planned(
        WHY_SEVERAL_OBJECTIVES,
        "Why several objectives?",
        "Why Transept optimises sequence and structure at the same time, and what a set of "
        "alignments gives you that a single one does not. No mathematics needed.",
        (
            "Sequence and structure often disagree: an example where improving one worsens the "
            "other",
            "Two ways out: weigh them in advance, or find every compromise at once",
            "Dominance and the front, explained with the chart of Results",
            "What to do with the front: the knee, your own weights, the medoid",
            "The set as a source of information: how robust each column is",
            "And with a single objective? What is lost",
        ),
    ),
    Planned(
        WHAT_TRANSEPT_OPTIMISES,
        "What Transept optimises",
        "The objectives in detail: what SOPwTP, lDDT and coverage measure, how to read their "
        "values, and what none of them can tell you.",
        (
            "The topology: transmembrane residues and transmembrane gaps",
            "SOPwTP, the topology-aware sum of pairs, with a worked example",
            "lDDT, consistency with the structures, without superposition or reference",
            "The limits of lDDT: helices out of register, and fewer aligned residues",
            "Coverage, the third objective, and why it exists",
            "The three formulations, and when to use each one",
            "What no objective measures: correctness against a reference",
        ),
    ),
    Planned(
        CHOOSE_AN_ALGORITHM,
        "Choose an algorithm",
        "NSGA-II, the reference multiobjective algorithm and the default of Transept, and the "
        "other algorithms for those who want to explore. The defaults are a good choice.",
        (
            "NSGA-II in a few steps, and why it is the default",
            "Why the default configuration is enough for most users",
            "The other algorithms, in one line each, and when to try them",
            "Highly configurable: NSGA-II, SPEA2 and the genetic algorithm, through their "
            "parameter spaces",
            "How to compare algorithms on your proteins: independent runs",
        ),
    ),
)


def learning_path(directory: Path | None = None) -> list[Tutorial | Planned]:
    """The tutorials of Learn in reading order: those written and those still coming."""
    written = list_tutorials(directory)
    names = {item.name for item in written}
    coming = [item for item in PLANNED if item.name not in names]
    return sorted([*written, *coming], key=lambda item: reading_position(item.name))


def tutorial_named(name: str, directory: Path | None = None) -> Tutorial | None:
    """Returns a tutorial by the name of its file, if it exists."""
    return next((item for item in list_tutorials(directory) if item.name == name), None)
