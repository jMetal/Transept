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
RELATIVE_LINK = re.compile(r"\]\((?![a-zA-Z][a-zA-Z0-9+.-]*:|#)([^)\s]+)\)")


@dataclass(slots=True, frozen=True)
class Tutorial:
    """A tutorial.

    Attributes:
        name: The name of its file, without the extension.
        title: Its first heading.
        text: Its Markdown, with links that also work outside the repository.
    """

    name: str
    title: str
    text: str


def absolute_links(text: str) -> str:
    """Points the relative links of a tutorial to the repository, which Transept does not serve."""

    def to_repository(match: re.Match) -> str:
        target = posixpath.normpath(posixpath.join(DIRECTORY, match.group(1)))
        return f"]({REPOSITORY_URL}/{target})"

    return RELATIVE_LINK.sub(to_repository, text)


def read_tutorial(path: Path) -> Tutorial:
    """Reads a tutorial; its title is its first heading, or else the name of the file."""
    text = path.read_text(encoding="utf-8")
    title = next(
        (line[2:].strip() for line in text.splitlines() if line.startswith("# ")), path.stem
    )
    return Tutorial(path.stem, title, absolute_links(text))


def list_tutorials(directory: Path | None = None) -> list[Tutorial]:
    """Returns the tutorials: the overview first, and the others by the name of their files."""
    folder = directory or settings.REPOSITORY / DIRECTORY
    paths = sorted(folder.glob("*.md"), key=lambda path: (path.stem != OVERVIEW, path.stem))
    return [read_tutorial(path) for path in paths]


def tutorial_named(name: str, directory: Path | None = None) -> Tutorial | None:
    """Returns a tutorial by the name of its file, if it exists."""
    return next((item for item in list_tutorials(directory) if item.name == name), None)
