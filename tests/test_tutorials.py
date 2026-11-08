"""The tutorials, read inside Transept."""

from pathlib import Path

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

    def test_should_keep_absolute_links_and_anchors(self):
        text = "[a](https://example.org/x) [b](#step-1) [c](mailto:a@example.org)"
        assert tutorials.absolute_links(text) == text


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

    def test_should_link_every_tutorial_to_files_that_exist(self):
        root = settings.REPOSITORY
        for path in (root / tutorials.DIRECTORY).glob("*.md"):
            for target in tutorials.RELATIVE_LINK.findall(path.read_text(encoding="utf-8")):
                assert (path.parent / target).exists(), f"{path.name}: {target}"
