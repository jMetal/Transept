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


def list_tutorials(directory: Path | None = None) -> list[Tutorial]:
    """Returns the tutorials: the overview first, and the others by the name of their files."""
    folder = directory or settings.REPOSITORY / DIRECTORY
    paths = sorted(folder.glob("*.md"), key=lambda path: (path.stem != OVERVIEW, path.stem))
    return [read_tutorial(path) for path in paths]


def tutorial_named(name: str, directory: Path | None = None) -> Tutorial | None:
    """Returns a tutorial by the name of its file, if it exists."""
    return next((item for item in list_tutorials(directory) if item.name == name), None)
