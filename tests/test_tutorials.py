"""The tutorials, read inside Transept."""

from pathlib import Path

from transept import tutorials


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
