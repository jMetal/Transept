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
GAPS_INSIDE_HELICES = "gaps-inside-helices"
# The levels of the tutorials, as the table at the top of each one gives it ("| **Level** | ... |");
# a tutorial without it is Basic. Learn groups them by level.
LEVELS = ("Basic", "Intermediate", "Advanced")
LEVEL = re.compile(r"^\|\s*\*\*Level\*\*\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
# What every written tutorial is for, for its card in Learn.
SUMMARIES = {
    "overview": "What Transept is for, what it gives you, and the usual ways of working with it.",
    "add-your-own-proteins": "Add proteins from UniProt or from your files, align them and read "
    "the result, with eight aquaporins.",
    "is-my-alignment-reliable": "Read the tracks of support, AlphaFold confidence and "
    "conservation, and check receptors against GPCRdb.",
    "operators": "The crossovers and mutations of the search, their settings, and when each one "
    "helps.",
    "why-several-objectives": "Why Transept optimises sequence and structure at the same time, "
    "and what a set of alignments gives you that a single one does not. No mathematics needed.",
    "what-transept-optimises": "The objectives in detail: what SOPwTP, lDDT and coverage "
    "measure, how to read their values, and what none of them can tell you.",
    "choose-an-algorithm": "How the search works, NSGA-II and why its defaults are enough, and the "
    "other algorithms for those who want to explore them.",
    "gaps-inside-helices": "Why gaps inside helices are a problem, and how Transept repairs "
    "them in any alignment or in the seeds of a search.",
}
# Within a level, the order in which the tutorials are meant to be read; the others follow, by
# file name.
READING_ORDER = (
    OVERVIEW,
    ADD_YOUR_OWN_PROTEINS,
    WHY_SEVERAL_OBJECTIVES,
    WHAT_TRANSEPT_OPTIMISES,
    RELIABILITY,
    GAPS_INSIDE_HELICES,
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
        level: One of LEVELS.
        summary: What it is for, for its card in Learn; empty if unknown.
    """

    name: str
    title: str
    text: str
    directory: Path | None = None
    level: str = LEVELS[0]
    summary: str = ""


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
    found = LEVEL.search(text)
    level = found.group(1).strip() if found else LEVELS[0]
    return Tutorial(
        path.stem,
        title,
        absolute_links(text),
        path.parent,
        level if level in LEVELS else LEVELS[0],
        SUMMARIES.get(path.stem, ""),
    )


def reading_position(name: str, level: str = LEVELS[0]) -> tuple[int, int, str]:
    """Where a tutorial goes in Learn: by level, then by READING_ORDER, and then by name."""
    order = READING_ORDER.index(name) if name in READING_ORDER else len(READING_ORDER)
    return LEVELS.index(level) if level in LEVELS else 0, order, name


def list_tutorials(directory: Path | None = None) -> list[Tutorial]:
    """Returns the tutorials that are written, in the order in which they are meant to be read."""
    folder = directory or settings.REPOSITORY / DIRECTORY
    found = [read_tutorial(path) for path in folder.glob("*.md")]
    return sorted(found, key=lambda item: reading_position(item.name, item.level))


@dataclass(slots=True, frozen=True)
class Planned:
    """A tutorial that is not written yet, shown in Learn as coming soon.

    Attributes:
        name: The name its file will have, without the extension.
        title: Its title.
        summary: What it is for, in a sentence or two.
        contents: What it will cover, one item each.
        level: One of LEVELS.
    """

    name: str
    title: str
    summary: str
    contents: tuple[str, ...]
    level: str = LEVELS[0]


# Tutorials still to be written, shown in Learn as coming soon until their file exists.
PLANNED: tuple[Planned, ...] = ()


def learning_path(directory: Path | None = None) -> list[Tutorial | Planned]:
    """The tutorials of Learn in reading order: those written and those still coming."""
    written = list_tutorials(directory)
    names = {item.name for item in written}
    coming = [item for item in PLANNED if item.name not in names]
    return sorted([*written, *coming], key=lambda item: reading_position(item.name, item.level))


def by_level(items: list[Tutorial | Planned]) -> dict[str, list[Tutorial | Planned]]:
    """The tutorials of Learn grouped by level, every level present, in reading order."""
    return {level: [item for item in items if item.level == level] for level in LEVELS}


def tutorial_named(name: str, directory: Path | None = None) -> Tutorial | None:
    """Returns a tutorial by the name of its file, if it exists."""
    return next((item for item in list_tutorials(directory) if item.name == name), None)
