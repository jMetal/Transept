"""The tutorials, read inside Transept."""

from pathlib import Path

import pytest

from transept import settings, tutorials


class TestAbsoluteLinks:
    def test_should_point_relative_links_to_the_repository(self):
        assert tutorials.absolute_links("See [it](../../README.md).") == (
            f"See [it]({tutorials.REPOSITORY_URL}/README.md)."
        )

    def test_should_resolve_a_link_in_the_same_folder(self):
        assert tutorials.absolute_links("[next](other.md)") == (
            f"[next]({tutorials.REPOSITORY_URL}/docs/tutorials/other.md)"
        )

    def test_should_leave_images_alone(self):
        text = "![The front](images/front.png)"
        assert tutorials.absolute_links(text) == text

    def test_should_keep_absolute_links_and_anchors(self):
        text = "[a](https://example.org/x) [b](#step-1) [c](mailto:a@example.org)"
        assert tutorials.absolute_links(text) == text


class TestParts:
    def test_should_split_the_text_at_its_images(self, tmp_path: Path):
        # Arrange
        (tmp_path / "images").mkdir()
        (tmp_path / "images" / "front.png").write_bytes(b"png")
        (tmp_path / "guide.md").write_text(
            "# Guide\n\nBefore.\n\n![The front](images/front.png)\n\nAfter.\n"
        )
        tutorial = tutorials.read_tutorial(tmp_path / "guide.md")

        # Act
        found = tutorials.parts(tutorial)

        # Assert
        assert "Before." in found[0]
        assert found[1] == tutorials.Figure(tmp_path / "images" / "front.png", "The front")
        assert "After." in found[2]

    def test_should_keep_an_image_without_file_as_text(self, tmp_path: Path):
        (tmp_path / "guide.md").write_text("# Guide\n\n![Missing](images/none.png)\n")
        tutorial = tutorials.read_tutorial(tmp_path / "guide.md")

        found = tutorials.parts(tutorial)

        assert len(found) == 1
        assert "![Missing](images/none.png)" in found[0]

    def test_should_find_the_file_of_every_figure_of_the_tutorials(self):
        for tutorial in tutorials.list_tutorials():
            for match in tutorials.IMAGE.finditer(tutorial.text):
                assert (tutorial.directory / match.group(2)).is_file(), (
                    f"{tutorial.name}: {match.group(2)}"
                )


FUTURE = tutorials.Planned(
    "future", "A future tutorial", "What it is for.", ("One thing", "Another"), "Intermediate"
)


@pytest.fixture
def planned(monkeypatch: pytest.MonkeyPatch) -> tutorials.Planned:
    """A tutorial still to be written, as if it were in PLANNED."""
    monkeypatch.setattr(tutorials, "PLANNED", (FUTURE,))
    return FUTURE


class TestLearningPath:
    def test_should_follow_the_reading_order_and_then_the_file_names(self, tmp_path: Path):
        for name in ("zeta", tutorials.OPERATORS, tutorials.OVERVIEW, tutorials.RELIABILITY):
            (tmp_path / f"{name}.md").write_text(f"# {name}\n")

        found = [item.name for item in tutorials.list_tutorials(tmp_path)]

        assert found == [tutorials.OVERVIEW, tutorials.RELIABILITY, tutorials.OPERATORS, "zeta"]

    def test_should_show_the_planned_tutorials_in_their_place(self, tmp_path: Path, planned):
        (tmp_path / f"{tutorials.OVERVIEW}.md").write_text("# Overview\n")
        (tmp_path / "advanced.md").write_text("# Advanced\n\n| **Level** | Advanced |\n")

        found = tutorials.learning_path(tmp_path)

        # Assert: by level: Basic, then the planned one (Intermediate), then Advanced
        assert [item.name for item in found] == [tutorials.OVERVIEW, "future", "advanced"]
        assert found[1] is planned

    def test_should_read_the_level_from_the_table_of_the_tutorial(self, tmp_path: Path):
        (tmp_path / "a.md").write_text("# A\n\n| | |\n| --- | --- |\n| **Level** | Advanced |\n")
        (tmp_path / "b.md").write_text("# B\n")
        (tmp_path / "c.md").write_text("# C\n\n| **Level** | Expert |\n")

        levels = {item.name: item.level for item in tutorials.list_tutorials(tmp_path)}

        assert levels == {"a": "Advanced", "b": "Basic", "c": "Basic"}

    def test_should_group_by_level_in_reading_order(self, tmp_path: Path, planned):
        (tmp_path / f"{tutorials.OVERVIEW}.md").write_text("# Overview\n")

        found = tutorials.by_level(tutorials.learning_path(tmp_path))

        assert list(found) == list(tutorials.LEVELS)
        assert [item.name for item in found["Basic"]] == [tutorials.OVERVIEW]
        assert found["Intermediate"] == [planned]
        assert found["Advanced"] == []

    def test_should_drop_a_planned_tutorial_once_it_is_written(self, tmp_path: Path, planned):
        (tmp_path / "future.md").write_text("# Future\n")

        found = tutorials.learning_path(tmp_path)

        assert len(found) == 1
        assert isinstance(found[0], tutorials.Tutorial)

    def test_should_give_every_written_tutorial_a_level_and_a_summary(self):
        for tutorial in tutorials.list_tutorials():
            assert tutorial.level in tutorials.LEVELS
            assert tutorial.summary, tutorial.name

    def test_should_place_the_written_tutorials_in_their_levels(self):
        found = tutorials.by_level(tutorials.learning_path())

        assert {level: [item.name for item in items] for level, items in found.items()} == {
            "Basic": [tutorials.OVERVIEW, tutorials.ADD_YOUR_OWN_PROTEINS, tutorials.RELIABILITY],
            "Intermediate": [tutorials.WHY_SEVERAL_OBJECTIVES, tutorials.WHAT_TRANSEPT_OPTIMISES],
            "Advanced": [tutorials.CHOOSE_AN_ALGORITHM, tutorials.OPERATORS],
        }


class TestListTutorials:
    def test_should_read_the_title_and_order_by_file(self, tmp_path: Path):
        # Arrange
        (tmp_path / "b.md").write_text("Intro\n\n# Second\n")
        (tmp_path / "a.md").write_text("# First\n")
        (tmp_path / "notes.txt").write_text("# Not a tutorial\n")

        # Act
        found = tutorials.list_tutorials(tmp_path)

        # Assert
        assert [(item.name, item.title) for item in found] == [("a", "First"), ("b", "Second")]

    def test_should_put_the_overview_first(self, tmp_path: Path):
        (tmp_path / "add.md").write_text("# Add\n")
        (tmp_path / "overview.md").write_text("# Overview\n")
        found = tutorials.list_tutorials(tmp_path)
        assert [item.name for item in found] == ["overview", "add"]

    def test_should_use_the_file_name_without_a_heading(self, tmp_path: Path):
        (tmp_path / "plain.md").write_text("No heading\n")
        assert tutorials.list_tutorials(tmp_path)[0].title == "plain"

    def test_should_find_nothing_in_an_empty_folder(self, tmp_path: Path):
        assert tutorials.list_tutorials(tmp_path) == []
        assert tutorials.tutorial_named("any", tmp_path) is None

    def test_should_find_the_tutorial_of_add_dataset(self):
        tutorial = tutorials.tutorial_named(tutorials.ADD_YOUR_OWN_PROTEINS)
        assert tutorial is not None
        assert tutorial.title == "Add your own proteins"
        assert "../../" not in tutorial.text

    def test_should_find_the_tutorial_of_the_operators(self):
        tutorial = tutorials.tutorial_named(tutorials.OPERATORS)
        assert tutorial is not None
        assert tutorial.title == "Choose the operators"

    def test_should_find_the_tutorial_on_reliability(self):
        tutorial = tutorials.tutorial_named(tutorials.RELIABILITY)
        assert tutorial is not None
        assert tutorial.title == "Is my alignment reliable?"

    def test_should_link_every_tutorial_to_files_that_exist(self):
        root = settings.REPOSITORY
        for path in (root / tutorials.DIRECTORY).glob("*.md"):
            for _, target in tutorials.RELATIVE_LINK.findall(path.read_text(encoding="utf-8")):
                assert (path.parent / target).exists(), f"{path.name}: {target}"
