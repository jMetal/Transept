"""The pages of Transept, grouped by use case: the single source of the menu and the home page.

`app.py` builds `st.navigation` from `SECTIONS` and the home page shows a card for each page, so the
two cannot drift apart. A page without a script is announced on the home page as coming soon and
left out of the menu.
"""

from __future__ import annotations

from dataclasses import dataclass

from transept import ui


@dataclass(slots=True, frozen=True)
class Page:
    """A page of Transept.

    Attributes:
        title: Its title in the menu and on its card.
        icon: Its icon in the menu and on its card.
        description: What the user can do with it, for its card on the home page.
        path: Its script, relative to the root of the application; None if not available yet.
    """

    title: str
    icon: str
    description: str
    path: str | None = None

    @property
    def available(self) -> bool:
        return self.path is not None


@dataclass(slots=True, frozen=True)
class Section:
    """A group of pages in the menu.

    Attributes:
        name: Its heading in the menu, and the label of the cards of its pages.
        pages: Its pages, in menu order.
    """

    name: str
    pages: tuple[Page, ...]

    @property
    def available_pages(self) -> tuple[Page, ...]:
        return tuple(page for page in self.pages if page.available)


SECTIONS = (
    Section(
        "Explore",
        (
            Page(
                "Datasets",
                ":material/dataset:",
                "See the datasets of your data directories and whether they are ready to use, and "
                "add other directories, such as the GPCR structural benchmark.",
                ui.DATASETS,
            ),
            Page(
                "Add dataset",
                ":material/add_circle:",
                "Add your own proteins: a checklist guides you through the files needed (sequences "
                "and topology, structures, seed and reference alignments).",
                ui.ADD_DATASET,
            ),
            Page(
                "Algorithms",
                ":material/category:",
                "Browse the algorithms, objectives and operators you can optimise with, and the "
                "parameters of each configurable algorithm.",
            ),
        ),
    ),
    Section(
        "Optimize",
        (
            Page(
                "New run",
                ":material/play_arrow:",
                "Choose a dataset, the seed alignments, the objectives and an algorithm with its "
                "configuration, and launch the search.",
                ui.NEW_RUN,
            ),
            Page(
                "Monitor",
                ":material/monitoring:",
                "Follow a run live, with its evaluations and best values; cancel it, or find out "
                "why it failed.",
                ui.MONITOR,
            ),
            Page(
                "History",
                ":material/history:",
                "Every run with its state: open one in the monitor or the results, or move runs to "
                "the trash.",
                ui.HISTORY,
            ),
        ),
    ),
    Section(
        "Analyze",
        (
            Page(
                "Results",
                ":material/scatter_plot:",
                "Explore the alignments of a finished run: pick one from the chart, browse it "
                "helix by helix, compare it with the seed alignments and download it.",
                ui.RESULTS,
            ),
            Page(
                "Compare",
                ":material/compare_arrows:",
                "Compare runs, seed alignments and alignments of other tools, against a reference "
                "alignment when there is one.",
            ),
        ),
    ),
    Section(
        "Advanced",
        (
            Page(
                "Automatic configuration",
                ":material/tune:",
                "Let Transept search for a good configuration of an algorithm on a set of "
                "datasets.",
            ),
        ),
    ),
    Section(
        "Learn",
        (
            Page(
                "Tutorials",
                ":material/school:",
                "Step-by-step guides, such as how to add and align your own proteins.",
                ui.TUTORIALS,
            ),
        ),
    ),
)
