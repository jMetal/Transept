"""The sections are the single source of the menu and the home page."""

from pathlib import Path

from transept import ui
from transept.sections import SECTIONS, Page

ROOT = Path(__file__).resolve().parent.parent
ALL_PAGES = [page for section in SECTIONS for page in section.pages]


class TestPage:
    def test_should_be_available_only_with_a_script(self):
        assert Page("Title", ":material/home:", "Description", "pages/home.py").available
        assert not Page("Title", ":material/home:", "Description").available


class TestSections:
    def test_should_follow_the_use_cases_in_order(self):
        names = [section.name for section in SECTIONS]
        assert names == ["Explore", "Optimize", "Analyze", "Advanced", "Learn"]

    def test_should_point_to_scripts_that_exist(self):
        for page in ALL_PAGES:
            if page.available:
                assert (ROOT / page.path).is_file(), page.path

    def test_should_offer_every_page_script_except_the_home_page(self):
        scripts = {f"pages/{path.name}" for path in (ROOT / "pages").glob("*.py")}
        offered = {page.path for page in ALL_PAGES if page.available}
        assert offered == scripts - {ui.HOME}

    def test_should_have_unique_titles_and_a_description(self):
        titles = [page.title for page in ALL_PAGES]
        assert len(titles) == len(set(titles))
        assert all(page.description for page in ALL_PAGES)

    def test_should_list_only_the_available_pages_of_a_section(self):
        optimize = next(section for section in SECTIONS if section.name == "Optimize")
        learn = next(section for section in SECTIONS if section.name == "Learn")
        assert [page.path for page in optimize.available_pages] == [
            ui.NEW_RUN,
            ui.MONITOR,
            ui.HISTORY,
        ]
        assert learn.available_pages == ()
