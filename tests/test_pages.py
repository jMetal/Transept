"""The pages open without errors and show what they should, without a browser."""

import json
import os
import shutil
import time
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from conftest import ALIGNMENTS, ALIVE_PID, THREE_LINE, pdb_text, write_finished_run, write_job
from streamlit.testing.v1 import AppTest

from transept import (
    algorithms,
    datasets,
    options,
    reference_scores,
    runner,
    runs,
    series,
    settings,
    tutorials,
    ui,
)
from transept.algorithms import Algorithm
from transept.sections import SECTIONS

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def open_page(page: str, **state) -> AppTest:
    app = AppTest.from_file(APP, default_timeout=30)
    for key, value in state.items():
        app.session_state[key] = value
    app.run()
    if page != ui.HOME:
        app.switch_page(page)
        app.run()
    return app


def texts(app: AppTest) -> str:
    parts = [element.value for element in app.markdown] + [element.value for element in app.caption]
    parts += [str(element.value) for element in app.success]
    parts += [str(element.value) for element in app.error]
    parts += [str(element.value) for element in app.warning]
    parts += [str(element.value) for element in app.info]
    return "\n".join(parts)


class TestHome:
    def test_should_report_what_is_missing(self, transept_home: Path):
        # Arrange
        settings.save_settings(settings.Settings("/no.jar"))

        # Act
        app = open_page(ui.HOME)

        # Assert
        assert not app.exception
        assert app.title[0].value.startswith("Transept: ")
        assert "jar was not found" in texts(app)
        assert next(b for b in app.button if b.label == "Run the example").disabled

    def test_should_say_it_is_ready(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        app = open_page(ui.HOME)
        assert not app.exception
        assert "1 dataset in 1 repository" in texts(app)

    def test_should_show_a_card_for_every_page(self, configured):
        # Act
        app = open_page(ui.HOME)

        # Assert
        assert not app.exception
        shown = texts(app) + "\n".join(link.proto.label for link in app.get("page_link"))
        for section in SECTIONS:
            for page in (page for page in section.pages if not page.is_tutorials):
                assert page.title in shown
                assert page.description in shown

    def test_should_summarise_the_activity_and_open_a_recent_run(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.HOME)

        # Assert: the state of every step, and the run listed under Analyze
        assert not app.exception
        shown = texts(app)
        assert "1 dataset in 1 repository" in shown
        assert "0 running · 1 run · 0 series" in shown
        assert "1 with results" in shown
        assert "**NSGA-II** on toy" in shown
        assert "Latest result: NSGA-II on toy (done). The knee is marked." in shown
        assert app.get("plotly_chart")

        # Act
        next(b for b in app.button if b.key == "home_open_toy / done").click().run()

        # Assert
        assert app.session_state[ui.SELECTED_RUN] == ("toy", "done")

    def test_should_show_what_transept_offers(self, configured):
        app = open_page(ui.HOME)
        assert not app.exception
        facts = {metric.label: metric.value for metric in app.metric}
        assert list(facts) == ["Datasets", "Algorithms", "Formulations", "Operators", "Tutorials"]
        assert facts["Datasets"] == "1"
        assert facts["Operators"] == str(len(options.CROSSOVERS) + len(options.MUTATIONS))

    def test_should_launch_the_example_and_follow_it(
        self, configured, monkeypatch: pytest.MonkeyPatch
    ):
        # Arrange: the run is not really launched
        launched = []
        monkeypatch.setattr(
            runner, "launch", lambda request, *args: launched.append(request) or Path("job")
        )
        app = open_page(ui.HOME)

        # Act
        next(b for b in app.button if b.label == "Run the example").click().run()

        # Assert
        assert not app.exception
        assert [request.dataset for request in launched] == ["classT2_19"]
        assert app.session_state[ui.SELECTED_RUN][0] == "classT2_19"

    def test_should_link_only_the_available_pages(self, configured):
        # Arrange
        pages = [page for section in SECTIONS for page in section.pages]

        # Act
        app = open_page(ui.HOME)

        # Assert
        assert not app.exception
        labels = {link.proto.label for link in app.get("page_link")}
        for page in pages:
            if not page.is_tutorials:
                assert (page.title in labels) == page.available, page.title
        assert texts(app).count("Coming soon") == sum(not page.available for page in pages)


class TestResultsAgainstTheReference:
    @staticmethod
    def metrics(rows: list[int], f1: list[float]) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "row": rows,
                reference_scores.PAIR_F1: f1,
                reference_scores.TM_PAIR_F1: [0.9] * len(rows),
                reference_scores.TM_GAP_RATE: [0.01] * len(rows),
                reference_scores.COVERAGE: [0.8] * len(rows),
            }
        )

    @pytest.fixture
    def scored(self, configured, data_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        write_finished_run(settings.runs_root(), data_root)
        reference = datasets.reference_file(data_root, "toy")
        reference.parent.mkdir(parents=True)
        reference.write_text(">p1\nA\n")
        table = self.metrics([0, 1, 3], [0.6, 0.7, 0.5])
        seeds = pd.DataFrame(
            {
                "seed": ["mafft", "kalign"],
                **{
                    name: [0.4, None] if name == reference_scores.PAIR_F1 else [0.5, None]
                    for name in reference_scores.METRICS
                },
                "problem": ["", "Protein IDs differ"],
            }
        )
        monkeypatch.setattr(reference_scores, "run_scores", lambda *arguments: table)
        monkeypatch.setattr(reference_scores, "seed_scores", lambda *arguments: seeds)

    def test_should_show_the_metrics_beside_the_best_and_the_seeds(self, scored):
        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        titles = [element.value for element in app.subheader]
        heading = next(title for title in titles if "against the reference" in title)
        assert heading.startswith("MSASol")
        labels = [element.label for element in app.metric]
        assert {"Pair F1", "TM-pair F1", "TM-gap rate", "Coverage"} <= set(labels)
        comparison = next(f.value for f in app.dataframe if "alignment" in f.value.columns)
        assert "MSASol1 (best of this run)" in list(comparison["alignment"])
        assert "seed: mafft" in list(comparison["alignment"])
        assert "seed: kalign" not in list(comparison["alignment"])
        assert "Seeds that could not be compared: kalign." in texts(app)

    def test_should_add_the_metrics_to_the_table_of_alignments(self, scored):
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))
        solutions = next(f.value for f in app.dataframe if "file" in f.value.columns)
        assert reference_scores.PAIR_F1 in solutions.columns

    def test_should_say_when_there_is_no_reference(self, configured, data_root: Path):
        write_finished_run(settings.runs_root(), data_root)
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))
        assert not app.exception
        assert "no reference alignment" in texts(app)

    def test_should_explain_when_the_jar_cannot_compare(self, scored, monkeypatch):
        monkeypatch.setattr(reference_scores, "run_scores", lambda *arguments: None)
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))
        assert not app.exception
        assert "could not be compared with the reference" in texts(app)


class TestSeries:
    @staticmethod
    def finished_series(root: Path, data_root: Path) -> None:
        directory = write_finished_run(root, data_root, "s_seed_1")
        write_finished_run(root, data_root, "s_seed_2")
        assert directory.is_dir()
        folder = series.series_directory(root, "toy", "s")
        folder.mkdir(parents=True)
        request = runner.RunRequest(dataset="toy", seeds=("mafft", "kalign"), run_id="s", seed=1)
        saved = {
            "dataset": "toy",
            "series_id": "s",
            "requests": [
                {name: getattr(member, name) for name in runner.RunRequest.__dataclass_fields__}
                for member in series.member_requests(request, 2)
            ],
            "parallel": 1,
            "jar": "/t.jar",
            "data_root": str(data_root),
            "runs_root": str(root),
        }
        (folder / series.SERIES_FILE).write_text(json.dumps(saved))
        for seed in (1, 2):
            (folder / f"started_{seed}").touch()

    def test_should_follow_a_series_in_the_monitor(self, configured, data_root: Path):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.MONITOR, selected_series="toy / s")

        # Assert
        assert not app.exception
        assert "toy / s: finished" in [element.value for element in app.subheader]
        table = app.dataframe[0].value
        assert list(table["seed"]) == [1, 2]
        assert list(table["state"]) == ["finished", "finished"]
        assert "Every run has finished." in texts(app)

    def test_should_open_the_results_of_a_run_of_the_series(self, configured, data_root: Path):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)
        app = open_page(ui.MONITOR, selected_series="toy / s")

        # Act
        next(b for b in app.button if b.label == "Open the results of this run").click().run()

        # Assert
        assert not app.exception
        assert app.title[0].value == "Results"
        assert app.session_state[ui.SELECTED_RUN] == ("toy", "s_seed_1")

    def test_should_say_why_a_run_of_the_series_failed(self, configured, data_root: Path):
        # Arrange: a run of the series that failed
        root = settings.runs_root()
        self.finished_series(root, data_root)
        results = runner.run_directory(root, "toy", "s_seed_2")
        (results / "metadata.json").unlink()
        (results / "error.json").write_text('{"type": "Error", "message": "no seeds"}')
        app = open_page(ui.MONITOR, selected_series="toy / s")
        assert "toy / s: finished, with problems" in [e.value for e in app.subheader]
        assert "1 run(s) did not finish" in texts(app)

        # Act
        next(b for b in app.selectbox if b.label == "Run of the series").set_value("s_seed_2").run()

        # Assert
        assert not app.exception
        assert any("no seeds" in code.value for code in app.code)

    def test_should_offer_one_entry_per_series_or_single_run(self, configured, data_root: Path):
        # Arrange
        root = settings.runs_root()
        self.finished_series(root, data_root)
        write_finished_run(root, data_root, "alone")

        # Act
        app = open_page(ui.MONITOR)

        # Assert
        assert not app.exception
        selector = next(box for box in app.selectbox if box.label == "Run")
        assert sorted(selector.options) == ["toy / alone", "toy / s (2 runs)"]

    def test_should_show_a_single_run_as_before(self, configured, data_root: Path):
        # Arrange
        root = settings.runs_root()
        self.finished_series(root, data_root)
        write_finished_run(root, data_root, "alone")

        # Act
        app = open_page(ui.MONITOR, selected_run=("toy", "alone"))

        # Assert
        assert not app.exception
        assert "toy / alone: finished" in [element.value for element in app.subheader]

    def test_should_show_the_aggregate_in_results_by_default(self, configured, data_root: Path):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.RESULTS, selected_series="toy / s")

        # Assert
        assert not app.exception
        show = next(box for box in app.selectbox if box.label == "Show")
        assert show.value == "All runs (aggregate)"
        assert show.options == ["All runs (aggregate)", "seed 1", "seed 2"]
        titles = [element.value for element in app.subheader]
        assert "Fronts of the runs and their aggregate" in titles
        table = next(f.value for f in app.dataframe if "seed" in f.value.columns)
        assert set(table["file"]) >= {"MSASol0.fasta"}

    def test_should_show_a_run_of_the_series_as_a_single_run(self, configured, data_root: Path):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)
        app = open_page(ui.RESULTS, selected_series="toy / s")

        # Act
        next(box for box in app.selectbox if box.label == "Show").set_value("seed 2").run()

        # Assert
        assert not app.exception
        titles = [element.value for element in app.subheader]
        assert "Non-dominated alignments" in titles
        assert "Fronts of the runs and their aggregate" not in titles

    def test_should_open_the_run_remembered_inside_its_series(self, configured, data_root: Path):
        # Arrange: as when coming from History or from a run in Monitor
        self.finished_series(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "s_seed_2"))

        # Assert
        assert not app.exception
        assert next(box for box in app.selectbox if box.label == "Show").value == "seed 2"

    def test_should_warn_about_a_partial_series(self, configured, data_root: Path):
        # Arrange
        root = settings.runs_root()
        self.finished_series(root, data_root)
        (runner.run_directory(root, "toy", "s_seed_2") / "metadata.json").unlink()

        # Act
        app = open_page(ui.RESULTS, selected_series="toy / s")

        # Assert
        assert not app.exception
        assert "1 of 2 runs have finished" in texts(app)

    def test_should_prepare_the_download_only_when_asked(self, configured, data_root: Path):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)
        app = open_page(ui.RESULTS, selected_series="toy / s")
        assert not app.get("download_button")

        # Act
        next(b for b in app.button if b.label.startswith("Prepare the")).click().run()

        # Assert
        assert not app.exception
        assert app.get("download_button")

    def test_should_show_the_metrics_of_a_series_against_the_reference(
        self, configured, data_root: Path, monkeypatch
    ):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)
        reference = datasets.reference_file(data_root, "toy")
        reference.parent.mkdir(parents=True)
        reference.write_text(">p1\nA\n")
        monkeypatch.setattr(
            reference_scores,
            "run_scores",
            lambda *arguments: TestResultsAgainstTheReference.metrics([0, 1, 3], [0.6, 0.7, 0.5]),
        )
        monkeypatch.setattr(
            reference_scores,
            "seed_scores",
            lambda *arguments: pd.DataFrame(columns=["seed", *reference_scores.METRICS, "problem"]),
        )

        # Act
        app = open_page(ui.RESULTS, selected_series="toy / s")

        # Assert
        assert not app.exception
        table = next(f.value for f in app.dataframe if "alignment" in f.value.columns)
        assert "(best of all runs)" in table["alignment"].iloc[0]
        solutions = next(f.value for f in app.dataframe if "file" in f.value.columns)
        assert reference_scores.PAIR_F1 in solutions.columns

    def test_should_filter_history_by_series(self, configured, data_root: Path):
        # Arrange
        root = settings.runs_root()
        self.finished_series(root, data_root)
        write_finished_run(root, data_root, "alone")
        app = open_page(ui.HISTORY)
        assert len(app.dataframe[0].value) == 3

        # Act
        next(box for box in app.selectbox if box.label == "Show").set_value("toy / s").run()

        # Assert
        assert not app.exception
        assert sorted(app.dataframe[0].value["run"]) == ["s_seed_1", "s_seed_2"]

    def test_should_delete_and_restore_a_whole_series(self, configured, data_root: Path):
        # Arrange
        root = settings.runs_root()
        self.finished_series(root, data_root)
        app = open_page(ui.HISTORY)
        next(box for box in app.selectbox if box.label == "Show").set_value("toy / s").run()

        # Act
        next(b for b in app.button if b.label.startswith("Delete the 2 runs")).click().run()
        next(b for b in app.button if b.label == "Yes, move them to the trash").click().run()

        # Assert
        assert not app.exception
        assert len(runs.list_trash(root)) == 2
        assert not runs.list_runs(root)

        # Act
        next(b for b in app.button if b.label == "Restore the 2 runs of toy / s").click().run()

        # Assert
        assert not app.exception
        assert len(runs.list_runs(root)) == 2
        assert runs.list_trash(root) == []

    def test_should_say_which_series_a_run_belongs_to(self, configured, data_root: Path):
        # Arrange
        self.finished_series(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.HISTORY)

        # Assert
        assert not app.exception
        assert list(app.dataframe[0].value["series"]) == ["s", "s"]


class TestAlgorithms:
    CATALOGUE = (
        Algorithm("NSGA_II", 2, 3, "MSANSGAII.yaml", False, False, True),
        Algorithm("GENETIC_ALGORITHM", 1, 1, "MSAGA.yaml", False, False, True),
        Algorithm("PAES", 2, 3, None, True, False, False),
    )

    @pytest.fixture
    def catalogue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(algorithms, "catalogue", lambda jar: self.CATALOGUE)

    def test_should_list_the_algorithms_of_the_jar(self, configured, catalogue):
        # Act
        app = open_page(ui.ALGORITHMS)

        # Assert
        assert not app.exception
        table = app.dataframe[0].value
        assert list(table["Algorithm"]) == ["NSGA_II", "GENETIC_ALGORITHM", "PAES"]
        assert list(table["Objectives"]) == ["2-3", "1", "2-3"]
        assert list(table["Parallel"]) == [True, True, False]
        assert "Asynchronous" not in table.columns
        assert not [button for button in app.button if button.label == "Use this algorithm"]

    def test_should_show_the_parameter_space_of_the_selected_one(self, configured, catalogue):
        # Act
        app = open_page(ui.ALGORITHMS, algorithms_selected="NSGA_II")

        # Assert
        assert not app.exception
        assert "**Parameter space**" in texts(app)
        names = list(app.dataframe[1].value["Parameter"])
        assert "algorithmResult" in names

    def test_should_filter_the_parameters(self, configured, catalogue):
        # Arrange
        app = open_page(ui.ALGORITHMS, algorithms_selected="NSGA_II")

        # Act
        app.text_input[0].set_value("no such parameter").run()

        # Assert
        assert not app.exception
        assert 'No parameter matches "no such parameter"' in texts(app)

    def test_should_show_the_notes_of_an_algorithm_without_a_space(self, configured, catalogue):
        app = open_page(ui.ALGORITHMS, algorithms_selected="PAES")
        assert not app.exception
        assert "does not use the crossover" in texts(app)
        assert "**Parameter space**" not in texts(app)

    def test_should_explain_objectives_and_operators(self, configured, catalogue):
        app = open_page(ui.ALGORITHMS)
        assert not app.exception
        assert algorithms.FORMULATION_DETAILS["LDDT"] in texts(app)
        assert algorithms.CROSSOVER in texts(app)

    def test_should_explain_when_the_jar_gives_no_catalogue(self, configured, monkeypatch):
        def fail(jar):
            raise algorithms.CatalogueError("no answer")

        monkeypatch.setattr(algorithms, "catalogue", fail)
        app = open_page(ui.ALGORITHMS)
        assert not app.exception
        assert "did not give its algorithms: no answer" in texts(app)
        assert algorithms.CROSSOVER in texts(app)


class TestResultsStructures:
    STRUCTURES = "Structures for ChimeraX and PyMOL (zip)"

    def test_should_offer_the_structures_when_there_are_models(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)
        models = data_root / "alphafold_pdb" / "toy"
        models.mkdir(parents=True)
        for protein in datasets.read_topology(datasets.topology_file(data_root, "toy"))[:2]:
            sequence = protein.residues
            (models / f"{protein.id}.pdb").write_text(pdb_text(len(sequence), sequence))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        labels = [button.proto.label for button in app.get("download_button")]
        assert self.STRUCTURES in labels

    def test_should_draw_the_superposed_traces(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)
        models = data_root / "alphafold_pdb" / "toy"
        models.mkdir(parents=True)
        for protein in datasets.read_topology(datasets.topology_file(data_root, "toy"))[:2]:
            sequence = protein.residues
            (models / f"{protein.id}.pdb").write_text(pdb_text(len(sequence), sequence))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        charts = [json.loads(chart.proto.spec) for chart in app.get("plotly_chart")]
        assert any(trace["type"] == "scatter3d" for chart in charts for trace in chart["data"])

    def test_should_list_the_residues_of_the_marked_column(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)
        models = data_root / "alphafold_pdb" / "toy"
        models.mkdir(parents=True)
        for protein in datasets.read_topology(datasets.topology_file(data_root, "toy"))[:2]:
            sequence = protein.residues
            (models / f"{protein.id}.pdb").write_text(pdb_text(len(sequence), sequence))
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))
        assert any(box.label.startswith("Column to mark") for box in app.selectbox)

        # Act
        next(b for b in app.button if b.label.startswith("Show column")).click().run()

        # Assert: the Alignment tab starts up to ten columns before it (the toy has nine columns)
        assert not app.exception
        start = next(slider for slider in app.slider if slider.label == "First column")
        assert start.value == 1
        assert "Residues of column" in texts(app)
        assert len(app.dataframe) >= 2

    def test_should_say_what_it_lacks_without_models(self, configured, data_root: Path):
        write_finished_run(settings.runs_root(), data_root)
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))
        assert not app.exception
        assert self.STRUCTURES not in [button.proto.label for button in app.get("download_button")]
        assert "needs the structure models of at least two" in texts(app)


class TestTutorials:
    def test_should_offer_every_tutorial_in_the_card_of_the_home_page(self, configured):
        # Act
        app = open_page(ui.HOME)

        # Assert
        assert not app.exception
        labels = [link.proto.label for link in app.get("page_link")]
        assert "New here? Read the overview" in labels
        for tutorial in tutorials.list_tutorials():
            assert tutorial.title in labels
        for planned in tutorials.PLANNED:
            assert planned.title in labels
        assert ":gray-badge[Coming soon]" in texts(app)

    def test_should_show_what_a_planned_tutorial_will_cover(self):
        def script() -> None:
            import streamlit as st

            from transept import tutorials, ui

            st.navigation([ui.planned_page(tutorials.PLANNED[0])]).run()

        # Act
        app = AppTest.from_function(script, default_timeout=30).run()

        # Assert
        assert not app.exception
        shown = "\n".join(element.value for element in app.markdown)
        assert "Coming soon" in shown
        assert "What it will cover" in shown

    def test_should_show_a_tutorial_as_a_page_of_the_menu(self):
        def script() -> None:
            import streamlit as st

            from transept import ui

            st.navigation(ui.tutorial_pages()).run()

        # Act
        app = AppTest.from_function(script, default_timeout=30).run()

        # Assert: the overview comes first, so it opens by default
        assert not app.exception
        assert app.markdown[0].value.startswith("# Overview")

    def test_should_work_without_tutorials(self, configured, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(tutorials, "list_tutorials", lambda directory=None: [])
        app = open_page(ui.HOME)
        assert not app.exception


class TestDatasets:
    def test_should_list_the_datasets_with_their_checklist(self, configured):
        # Act
        app = open_page(ui.DATASETS)

        # Assert
        assert not app.exception
        table = app.dataframe[0].value
        assert list(table["Dataset"]) == ["toy"]
        assert table["Structures"][0] == "2/3"
        assert table["Status"][0] == "Ready, with warnings"
        assert "toy · Toy" in [element.value for element in app.subheader]
        assert "1 of 3 proteins have no distances" in texts(app)

    def test_should_add_a_repository_and_refuse_a_wrong_directory(self, configured, tmp_path: Path):
        # Arrange
        other = tmp_path / "Other"
        (other / "sequences" / "tmregions").mkdir(parents=True)
        app = open_page(ui.DATASETS)

        # Act: a directory without the layout
        app.text_input[0].set_value(str(tmp_path / "wrong"))
        next(button for button in app.button if button.label == "Add").click().run()

        # Assert
        assert "does not look like a data directory" in texts(app)
        assert len(settings.load_settings().repositories) == 1

        # Act: a repository
        app.text_input[0].set_value(str(other))
        next(button for button in app.button if button.label == "Add").click().run()

        # Assert
        assert not app.exception
        names = [repository.name for repository in settings.load_settings().repositories]
        assert names == ["Toy", "Other"]

    def test_should_show_a_missing_repository_without_failing(self, configured, tmp_path: Path):
        # Arrange
        gone = settings.Repository("Gone", str(tmp_path / "gone"))
        settings.save_settings(settings.Settings(configured.jar, [*configured.repositories, gone]))

        # Act
        app = open_page(ui.DATASETS)

        # Assert
        assert not app.exception
        assert "Directory not found" in texts(app)
        assert list(app.dataframe[0].value["Dataset"]) == ["toy"]

    def test_should_not_offer_to_optimize_a_dataset_that_cannot_be_used(
        self, configured, data_root: Path
    ):
        # Arrange
        topology = data_root / "sequences" / "tmregions" / "toy_predicted_topologies.3line"
        topology.write_text(">only\nAC\n")

        # Act
        app = open_page(ui.DATASETS)

        # Assert
        assert not app.exception
        assert app.dataframe[0].value["Status"][0] == "Not usable"
        optimize = next(b for b in app.button if b.label == "Optimize this dataset")
        assert optimize.disabled


class FakeUpload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self.data = data
        self.size = len(data)

    def getvalue(self) -> bytes:
        return self.data


class TestAddDataset:
    @pytest.fixture
    def uploads(self, monkeypatch: pytest.MonkeyPatch) -> dict:
        """What the file uploaders return, by the start of their label (AppTest cannot upload)."""
        given: dict = {}

        def uploader(label, accept_multiple_files=False, **options):
            for start, value in given.items():
                if label.startswith(start):
                    return value
            return [] if accept_multiple_files else None

        monkeypatch.setattr(st, "file_uploader", uploader)
        return given

    @staticmethod
    def fill(app: AppTest) -> None:
        app.text_input[0].set_value("mine").run()
        app.button_group[0].set_value("From my files").run()
        next(button for button in app.button if button.label == "Check the files").click().run()

    def test_should_build_a_dataset_from_uniprot(self, configured, monkeypatch, tmp_path):
        # Arrange: what UniProt and AlphaFold DB would give for two proteins of the toy dataset
        from transept import uniprot_import

        models = {}
        for number, residues in ((1, 3), (2, 4)):
            path = tmp_path / f"p{number}.pdb"
            path.write_text(pdb_text(residues))
            models[f"p{number}"] = path
        entries = (
            uniprot_import.Entry("Q00001", "p1", "One", "ACD", "MMM", 1),
            uniprot_import.Entry("Q00002", "p2", "Two", "ACDE", "OMMO", 1),
        )
        asked = []

        def fetch(identifiers, progress=None, workers=4):
            asked.append(identifiers)
            return uniprot_import.Imported(entries, models, ("Q00003: not found in UniProt",))

        monkeypatch.setattr(uniprot_import, "fetch", fetch)
        app = open_page(ui.ADD_DATASET)
        app.text_input[0].set_value("mine").run()

        # Act: nothing is asked before the button
        app.text_area[0].set_value("Q00001 Q00002 Q00003").run()
        assert asked == []
        next(b for b in app.button if b.label == "Get them").click().run()
        next(b for b in app.button if b.label == "Check the files").click().run()

        # Assert
        assert not app.exception
        assert asked == [["Q00001", "Q00002", "Q00003"]]
        assert "Q00003: not found in UniProt" in texts(app)
        table = next(frame.value for frame in app.dataframe if "accession" in frame.value)
        assert list(table["protein"]) == ["p1", "p2"]
        assert "Distances computed from the PDB files of 2 protein(s)" in texts(app)
        assert not next(b for b in app.button if b.label == "Add to My datasets").disabled

    def test_should_offer_the_tutorial_on_the_same_page(self, configured):
        app = open_page(ui.ADD_DATASET)
        assert not app.exception
        assert app.expander[0].label == "Follow the tutorial"
        assert "Step 2: check them" in texts(app)

    def test_should_not_check_without_a_name_and_a_topology(self, configured):
        app = open_page(ui.ADD_DATASET)
        assert not app.exception
        assert next(b for b in app.button if b.label == "Check the files").disabled

    def test_should_add_a_dataset_after_checking_it(self, configured, uploads):
        # Arrange
        uploads["Sequences"] = FakeUpload("mine.3line", THREE_LINE.encode())
        uploads["PDB"] = [
            FakeUpload("p1.pdb", pdb_text(3).encode()),
            FakeUpload("p2.pdb", pdb_text(4).encode()),
            FakeUpload("other.pdb", pdb_text(3).encode()),
        ]
        app = open_page(ui.ADD_DATASET)

        # Act
        self.fill(app)

        # Assert: checked, and nothing added yet
        assert not app.exception
        assert "Distances computed from the PDB files of 2 protein(s)" in texts(app)
        assert "other.pdb" in texts(app)
        assert not settings.datasets_root().exists()

        # Act
        next(b for b in app.button if b.label == "Add to My datasets").click().run()

        # Assert
        assert not app.exception
        assert datasets.list_datasets(settings.datasets_root()) == ["mine"]
        assert app.title[0].value == "Datasets"
        assert app.session_state[ui.DATASET_SELECTED][1] == "mine"

    def test_should_not_add_a_dataset_that_cannot_be_used(self, configured, uploads):
        # Arrange: no structures
        uploads["Sequences"] = FakeUpload("mine.3line", THREE_LINE.encode())
        app = open_page(ui.ADD_DATASET)

        # Act
        self.fill(app)

        # Assert
        assert not app.exception
        assert "No protein has distances" in texts(app)
        assert next(b for b in app.button if b.label == "Add to My datasets").disabled

    def test_should_explain_why_the_files_cannot_make_a_dataset(self, configured, uploads):
        # Arrange
        uploads["Sequences"] = FakeUpload("mine.3line", b">a/b\nAC\nMM\n>c\nAC\nMM\n")
        app = open_page(ui.ADD_DATASET)

        # Act
        self.fill(app)

        # Assert
        assert not app.exception
        assert "cannot name a file" in texts(app)

    def test_should_discard_the_checklist_when_the_files_change(self, configured, uploads):
        # Arrange
        uploads["Sequences"] = FakeUpload("mine.3line", THREE_LINE.encode())
        app = open_page(ui.ADD_DATASET)
        self.fill(app)
        assert "Checklist of mine" in [element.value for element in app.subheader]

        # Act
        uploads["PDB"] = [FakeUpload("p1.pdb", pdb_text(3).encode())]
        app.run()

        # Assert
        assert not app.exception
        assert "Checklist of mine" not in [element.value for element in app.subheader]


class TestNewRun:
    def test_should_open_the_dataset_chosen_in_datasets(self, configured, tmp_path: Path):
        # Arrange: a dataset with the same name in another repository
        twin = tmp_path / "Twin"
        shutil.copytree(configured.repositories[0].path, twin)
        repositories = [*configured.repositories, settings.Repository("Twin", str(twin))]
        settings.save_settings(settings.Settings(configured.jar, repositories))

        # Act
        app = open_page(ui.NEW_RUN, dataset_to_optimize=(str(twin), "toy"))

        # Assert
        assert not app.exception
        selector = next(box for box in app.selectbox if box.label == "Dataset")
        assert selector.value == "toy (Twin)"
        assert selector.options == ["toy (Toy)", "toy (Twin)"]
        command = next(code.value for code in app.code if "--data-root" in code.value)
        assert str(twin) in command

    def test_should_share_the_cores_when_the_algorithm_is_not_parallel(
        self, configured, monkeypatch
    ):
        # Arrange
        monkeypatch.setattr(os, "cpu_count", lambda: 2)
        launched = []

        def fake_launch(request, count, parallel, jar, data_root, root):
            launched.append((request.threads, parallel))
            return series.Series("toy", request.run_id, root, (), parallel, jar, data_root, root)

        monkeypatch.setattr(series, "launch", fake_launch)
        app = open_page(ui.NEW_RUN)
        next(box for box in app.selectbox if box.label == "Algorithm").set_value("PAES").run()
        assert not [box for box in app.number_input if box.label == "Evaluation threads"]

        # Act
        next(box for box in app.number_input if box.label == "Independent runs").set_value(3).run()
        assert "up to 2 at a time" in texts(app)
        next(button for button in app.button if button.label == "Launch").click().run()

        # Assert
        assert not app.exception
        assert launched == [(1, 2)]

    def test_should_offer_the_settings_of_the_operators_with_their_defaults(self, configured):
        # Act: an algorithm not configured from a parameter space
        app = open_page(ui.NEW_RUN)
        next(box for box in app.selectbox if box.label == "Algorithm").set_value("SMS_EMOA").run()

        # Assert
        assert not app.exception
        shift = next(b for b in app.number_input if b.label == "Largest gap shift (columns)")
        cuts = next(b for b in app.number_input if b.label == "Candidate cuts of the crossover")
        assert (shift.value, cuts.value) == (0, 1)
        assert "0 means no limit" in shift.help
        command = next(code.value for code in app.code if "--data-root" in code.value)
        assert "--max-shift" not in command

        # Act
        shift.set_value(10).run()

        # Assert
        command = next(code.value for code in app.code if "--data-root" in code.value)
        assert "--max-shift 10" in command

    def test_should_explain_the_operators_in_new_run(self, configured):
        app = open_page(ui.NEW_RUN)
        assert not app.exception
        assert "How to choose the operators" in [item.label for item in app.expander]
        assert "# Choose the operators" in texts(app)

    def test_should_offer_the_uniform_crossover(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)
        next(box for box in app.selectbox if box.label == "Algorithm").set_value("SMS_EMOA").run()
        assert "Candidate cuts of the crossover" in [box.label for box in app.number_input]

        # Act
        next(box for box in app.selectbox if box.label == "Crossover").set_value(
            "TM_SAFE_UNIFORM"
        ).run()

        # Assert: the candidate cuts belong to the single-point crossover
        assert not app.exception
        assert "Candidate cuts of the crossover" not in [box.label for box in app.number_input]
        command = next(code.value for code in app.code if "--data-root" in code.value)
        assert "--crossover TM_SAFE_UNIFORM" in command

    def test_should_offer_the_uniform_crossover_in_the_configuration(self, configured):
        app = open_page(ui.NEW_RUN)
        crossover = next(box for box in app.selectbox if box.label == "crossover")
        assert crossover.options == ["tmSafeSinglePoint", "tmSafeUniform"]
        assert "neither cuts" in crossover.help

    def test_should_offer_only_the_settings_that_apply(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)
        next(box for box in app.selectbox if box.label == "Algorithm").set_value("PAES").run()
        labels = [box.label for box in app.number_input]

        # Assert: PAES does not use the crossover
        assert "Largest gap shift (columns)" in labels
        assert "Candidate cuts of the crossover" not in labels
        assert "Crossover" not in [box.label for box in app.selectbox]

        # Act: this mutation moves no run at random
        next(box for box in app.selectbox if box.label == "Mutation").set_value(
            "MERGE_GAP_RUNS"
        ).run()

        # Assert
        assert "Largest gap shift (columns)" not in [box.label for box in app.number_input]

    def test_should_explain_the_settings_in_the_configuration_form(self, configured):
        app = open_page(ui.NEW_RUN)
        assert not app.exception
        shift = next(box for box in app.number_input if box.label == "maxShift")
        assert shift.value == 0
        assert "0 means no limit" in shift.help

    @pytest.mark.parametrize(
        ("mutation", "parameter", "default"),
        [("tmSafeBlockShift", "blockShift", 1), ("tmSafeWindowRealign", "realignWindow", 50)],
    )
    def test_should_show_the_parameter_of_each_new_mutation(
        self, configured, mutation, parameter, default
    ):
        # Arrange
        app = open_page(ui.NEW_RUN)

        # Act
        next(box for box in app.selectbox if box.label == "mutation").set_value(mutation).run()

        # Assert
        assert not app.exception
        boxes = [box for box in app.number_input if box.label.startswith(parameter)]
        assert [box.value for box in boxes] == [default]
        assert "maxShift" not in [box.label for box in app.number_input]

    def test_should_explain_the_external_archive(self, configured):
        app = open_page(ui.NEW_RUN)
        result = next(box for box in app.selectbox if box.label == "algorithmResult")
        assert "external archive" in result.help

    def test_should_keep_the_identifier_typed_when_the_clock_changes(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)
        identifier = next(box for box in app.text_input if box.label == "Run identifier")
        identifier.set_value("mine").run()

        # Act: the default used to depend on the second
        time.sleep(1.1)
        next(box for box in app.number_input if box.label == "Evaluations").set_value(500).run()

        # Assert
        assert not app.exception
        assert next(box for box in app.text_input if box.label == "Run identifier").value == "mine"

    def test_should_keep_the_suggested_identifier_when_the_clock_changes(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)
        before = next(box for box in app.text_input if box.label == "Run identifier").value

        # Act
        time.sleep(1.1)
        next(box for box in app.number_input if box.label == "Evaluations").set_value(500).run()

        # Assert
        assert next(box for box in app.text_input if box.label == "Run identifier").value == before

    def test_should_suggest_another_identifier_for_another_algorithm(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)
        assert next(b for b in app.text_input if b.label == "Run identifier").value.startswith(
            "nsga_ii-"
        )

        # Act
        next(b for b in app.selectbox if b.label == "Algorithm").set_value("PAES").run()

        # Assert
        assert next(b for b in app.text_input if b.label == "Run identifier").value.startswith(
            "paes-"
        )

    def test_should_keep_a_typed_identifier_for_another_algorithm(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)
        next(b for b in app.text_input if b.label == "Run identifier").set_value("mine").run()

        # Act
        next(b for b in app.selectbox if b.label == "Algorithm").set_value("PAES").run()

        # Assert
        assert next(b for b in app.text_input if b.label == "Run identifier").value == "mine"

    def test_should_offer_a_series_only_with_several_runs(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN)

        # Act
        next(box for box in app.number_input if box.label == "Independent runs").set_value(3).run()

        # Assert
        assert not app.exception
        assert "one after another" in texts(app)
        assert "_seed_<seed>" in texts(app)
        assert [box for box in app.text_input if box.label == "Series identifier"]

    def test_should_launch_a_series(self, configured, monkeypatch: pytest.MonkeyPatch):
        # Arrange
        launched = []

        def fake_launch(request, count, parallel, jar, data_root, root):
            launched.append((request.run_id, count, parallel))
            return series.Series("toy", request.run_id, root, (), parallel, jar, data_root, root)

        monkeypatch.setattr(series, "launch", fake_launch)
        app = open_page(ui.NEW_RUN)
        next(box for box in app.number_input if box.label == "Independent runs").set_value(3).run()
        next(box for box in app.text_input if box.label == "Series identifier").set_value("s").run()

        # Act
        next(button for button in app.button if button.label == "Launch").click().run()

        # Assert
        assert not app.exception
        assert launched == [("s", 3, 1)]
        assert app.session_state[ui.SELECTED_SERIES] == "toy / s"

    def test_should_open_the_algorithm_chosen_with_a_formulation_it_accepts(self, configured):
        # Act
        app = open_page(ui.NEW_RUN, algorithm_to_use="GENETIC_ALGORITHM")

        # Assert
        assert not app.exception
        assert next(b for b in app.selectbox if b.label == "Objectives").value == "LDDT"
        chosen = next(b for b in app.selectbox if b.label == "Algorithm")
        assert chosen.value == "GENETIC_ALGORITHM"
        command = next(code.value for code in app.code if "--algorithm" in code.value)
        assert "GENETIC_ALGORITHM" in command

    def test_should_keep_the_algorithm_only_while_the_objectives_allow_it(self, configured):
        # Arrange
        app = open_page(ui.NEW_RUN, algorithm_to_use="PAES")
        assert next(b for b in app.selectbox if b.label == "Algorithm").value == "PAES"

        # Act
        next(b for b in app.selectbox if b.label == "Objectives").set_value("LDDT").run()

        # Assert
        assert not app.exception
        chosen = next(b for b in app.selectbox if b.label == "Algorithm")
        assert chosen.value == options.algorithms_for("LDDT")[0]

    def test_should_refuse_a_dataset_that_cannot_be_used(self, configured, data_root: Path):
        # Arrange
        for path in (data_root / "distances" / "toy").iterdir():
            path.unlink()

        # Act
        app = open_page(ui.NEW_RUN)

        # Assert
        assert not app.exception
        assert "No protein has distances" in texts(app)
        assert not [button for button in app.button if button.label == "Launch"]

    def test_should_offer_the_datasets_and_default_seeds(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Act
        app = open_page(ui.NEW_RUN)

        # Assert
        assert not app.exception
        assert app.selectbox[0].value == "toy"
        assert app.multiselect[0].value == ["internal"]
        assert any("--dataset toy" in code.value for code in app.code)

    def test_should_hide_invalid_seeds_and_warn_about_structures(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Act
        app = open_page(ui.NEW_RUN)

        # Assert
        assert "broken" not in app.multiselect[0].options
        assert "residue 8 of 'p2'" in texts(app)
        assert "1 of 3 proteins have no structure" in texts(app)
        assert "3 proteins" in texts(app)

    def test_should_warn_about_the_known_issues_of_caretta(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Act
        app = open_page(ui.NEW_RUN)
        app.multiselect[0].set_value(["kalign", "mafft", "caretta"]).run()

        # Assert
        assert "misaligned" in texts(app)

    def test_should_block_the_launch_with_a_single_seed(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Act
        app = open_page(ui.NEW_RUN)
        app.multiselect[0].set_value(["mafft"]).run()

        # Assert
        assert "at least two seed" in texts(app)
        assert next(button for button in app.button if button.label == "Launch").disabled

    def test_should_pass_a_changed_configuration_and_a_time_limit(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Arrange
        app = open_page(ui.NEW_RUN)

        # Act
        selection = next(box for box in app.selectbox if box.label.startswith("selection"))
        selection.set_value("random").run()
        app.radio[0].set_value("Time").run()

        # Assert
        assert not app.exception
        command = next(code.value for code in app.code if "--dataset toy" in code.value)
        assert "--configuration '--selection random'" in command
        assert "--max-time 60" in command
        assert "--mutation " not in command

    def test_should_configure_spea2_and_warn_about_asynchronous_runs(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Arrange
        app = open_page(ui.NEW_RUN)

        # Act
        algorithm = next(box for box in app.selectbox if box.label == "Algorithm")
        algorithm.set_value("SPEA2").run()
        has_ranking = any(box.label.startswith("ranking") for box in app.selectbox)
        algorithm = next(box for box in app.selectbox if box.label == "Algorithm")
        algorithm.set_value("ASYNC_NSGA_II").run()

        # Assert
        assert not app.exception
        assert has_ranking
        assert "will not repeat exactly" in texts(app)
        command = next(code.value for code in app.code if "--dataset toy" in code.value)
        assert "--algorithm ASYNC_NSGA_II" in command
        assert "--mutation TM_SAFE_GAP_SHIFT" in command

    def test_should_filter_the_algorithms_by_the_objectives(self, configured):
        if settings.java_version() is None:
            pytest.skip("Java is not installed")
        # Arrange
        app = open_page(ui.NEW_RUN)

        # Act
        objectives = next(box for box in app.selectbox if box.label == "Objectives")
        objectives.set_value("LDDT").run()

        # Assert
        assert not app.exception
        algorithm = next(box for box in app.selectbox if box.label == "Algorithm")
        assert algorithm.value == "GENETIC_ALGORITHM"
        assert options.DESCRIPTIONS["NSGA_II"] not in algorithm.options
        command = next(code.value for code in app.code if "--dataset toy" in code.value)
        assert "--objectives LDDT" in command

    def test_should_send_to_the_settings_when_not_ready(self, transept_home: Path):
        settings.save_settings(settings.Settings("/no.jar"))
        app = open_page(ui.NEW_RUN)
        assert not app.exception
        assert "not ready" in texts(app)


class TestMonitor:
    def test_should_explain_why_a_run_failed(self, configured):
        # Arrange
        write_job(settings.runs_root(), "broken", 999_999, log="Error: Unable to access jarfile\n")

        # Act
        app = open_page(ui.MONITOR)

        # Assert
        assert not app.exception
        assert "failed" in texts(app)
        assert "Unable to access jarfile" in app.code[0].value

    def test_should_show_a_running_run_with_a_cancel_button(self, configured):
        # Arrange
        write_job(settings.runs_root(), "live", ALIVE_PID)

        # Act
        app = open_page(ui.MONITOR)

        # Assert
        assert not app.exception
        assert any(button.label == "Cancel the run" for button in app.button)

    def test_should_stop_a_running_run_and_keep_its_results(self, configured):
        # Arrange: a running run whose search has started
        write_job(settings.runs_root(), "live", ALIVE_PID)
        results = settings.runs_root() / "ejecuciones" / "toy" / "live"
        results.mkdir(parents=True)
        app = open_page(ui.MONITOR)

        # Act
        next(b for b in app.button if b.label == "Stop and keep the results").click().run()

        # Assert
        assert not app.exception
        assert (results / runner.STOP_FILE).is_file()
        assert "Stopping" in texts(app)

    def test_should_show_the_progress_by_time(self, configured):
        # Arrange
        job = write_job(settings.runs_root(), "timed", ALIVE_PID)
        directory = settings.runs_root() / "ejecuciones" / "toy" / "timed"
        directory.mkdir(parents=True)
        (directory / "config.json").write_text(
            json.dumps({"algorithmType": "NSGA_II", "maxEvaluations": None, "maxTimeSeconds": 60})
        )
        (directory / "progress.jsonl").write_text(
            '{"evaluations":300,"elapsedMs":15000,"best":{"SOPwTP":1.0,"lDDT":0.5}}\n'
        )

        # Act
        app = open_page(ui.MONITOR)

        # Assert
        assert not app.exception, job
        assert "15 of 60 s (300 evaluations so far)" in app.get("progress")[0].proto.text

    def test_should_show_every_objective_while_running(self, configured):
        # Arrange
        write_job(settings.runs_root(), "three", ALIVE_PID)
        directory = settings.runs_root() / "ejecuciones" / "toy" / "three"
        directory.mkdir(parents=True)
        (directory / "config.json").write_text(json.dumps({"maxEvaluations": 200}))
        (directory / "progress.jsonl").write_text(
            '{"evaluations":100,"elapsedMs":900,"best":{"SOPwTP":30.0,"lDDT":0.6,"coverage":0.9}}\n'
        )

        # Act
        app = open_page(ui.MONITOR)

        # Assert
        assert not app.exception
        assert [metric.label for metric in app.metric] == [
            "Elapsed",
            "Best SOPwTP",
            "Best lDDT",
            "Best coverage",
        ]

    def test_should_say_there_are_no_runs(self, configured):
        app = open_page(ui.MONITOR)
        assert "no runs" in texts(app)


class TestResults:
    def test_should_show_the_front_and_the_knee_alignment(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        assert "p3" in texts(app)  # protein without structure
        assert "UNVERIFIED" in texts(app)
        assert "gap runs inside transmembrane helices: 1" in texts(app)  # ACDE-GHIK

    def test_should_show_a_single_objective_run(self, configured, data_root: Path):
        # Arrange
        directory = write_finished_run(settings.runs_root(), data_root)
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["objectives"] = ["lDDT"]
        (directory / "metadata.json").write_text(json.dumps(metadata))
        (directory / "FUN.csv").write_text("0.5\n0.6\n0.5\n0.55\n")

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert: the best alignment (row 1) is selected, and the copies are counted
        assert not app.exception
        assert "Objectives of this run: lDDT." in texts(app)
        assert any(metric.label == "Best lDDT" for metric in app.metric)
        alignment = next(box for box in app.selectbox if box.label == "Alignment")
        assert alignment.value == 1

    def test_should_show_the_configuration_used(self, configured, data_root: Path):
        # Arrange
        directory = write_finished_run(settings.runs_root(), data_root)
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["configuration"] = "--selection random --mutation tmSafeGapShift"
        (directory / "metadata.json").write_text(json.dumps(metadata))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        assert any("--selection random" in code.value for code in app.code)

    def test_should_say_that_a_run_was_stopped_early(self, configured, data_root: Path):
        # Arrange
        directory = write_finished_run(settings.runs_root(), data_root)
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["stoppedByUser"] = True
        (directory / "metadata.json").write_text(json.dumps(metadata))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert: the toy run planned 200 evaluations and did 200
        assert not app.exception
        assert "stopped at your request after 200 of 200 evaluations" in texts(app)

    def test_should_say_there_are_no_finished_runs(self, configured):
        app = open_page(ui.RESULTS)
        assert "no finished runs" in texts(app)


class TestHistory:
    def test_should_list_every_run_with_its_state(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)
        write_job(settings.runs_root(), "live", ALIVE_PID)

        # Act
        app = open_page(ui.HISTORY)

        # Assert
        assert not app.exception
        table = app.dataframe[0].value
        assert sorted(table["state"]) == ["finished", "running"]


class TestChoosingAnAlignment:
    def test_should_take_only_new_choices_of_each_widget(self):
        # Arrange
        seen = {}

        # Act & Assert: a stale selection of the chart does not override a newer choice
        assert ui.new_choice(seen, "chart", 3) == 3
        assert ui.new_choice(seen, "chart", 3) is None
        assert ui.new_choice(seen, "table", 5) == 5
        assert ui.new_choice(seen, "chart", 3) is None
        assert ui.new_choice(seen, "chart", None) is None
        assert ui.new_choice(seen, "chart", 3) == 3

    def test_should_change_the_alignment_from_the_selector(self, configured, data_root: Path):
        # Arrange
        write_finished_run(settings.runs_root(), data_root)
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Act
        app.selectbox(key="selector:toy / done").set_value(3).run()

        # Assert
        assert not app.exception
        assert app.session_state["row:toy / done"] == 3
        assert app.selectbox(key="selector:toy / done").value == 3


class TestResultsThreeObjectives:
    def test_should_draw_the_front_in_3d_and_in_projections(self, configured, data_root: Path):
        # Arrange: a run of SOPwTP, lDDT and coverage
        directory = write_finished_run(settings.runs_root(), data_root)
        (directory / "FUN.csv").write_text("30,0.5,0.8\n25,0.6,0.7\n30,0.5,0.8\n20,0.55,0.9\n")
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["objectives"] = ["SOPwTP", "lDDT", "coverage"]
        (directory / "metadata.json").write_text(json.dumps(metadata))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert: the 3D view first, then a projection that can be clicked
        assert not app.exception
        view = next(radio for radio in app.radio if radio.label == "View")
        assert view.options == ["3D", "SOPwTP – lDDT", "SOPwTP – coverage", "lDDT – coverage"]
        assert any("scatter3d" in chart.proto.spec for chart in app.get("plotly_chart"))
        view.set_value("lDDT – coverage").run()
        assert not app.exception
        assert not any("scatter3d" in chart.proto.spec for chart in app.get("plotly_chart"))
        assert len(app.dataframe[0].value) == 3


class TestResultsFrontSummary:
    def test_should_say_how_much_the_alignments_of_the_front_agree(
        self, configured, data_root: Path
    ):
        write_finished_run(settings.runs_root(), data_root)

        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        assert not app.exception
        assert "The 2 alignments of the front share 100.0% of their residue pairs" in texts(app)
        assert "The knee is also the medoid" in texts(app)

    def test_should_compare_the_knee_and_the_medoid_when_they_differ(
        self, configured, data_root: Path
    ):
        # Arrange: three non-dominated alignments; the knee (row 2) has the alignment of row 0,
        # and row 1 another one, so the medoid is row 0, first in the front.
        directory = write_finished_run(settings.runs_root(), data_root)
        (directory / "FUN.csv").write_text("30.0,0.50\n25.0,0.60\n28.0,0.58\n")
        other = ALIGNMENTS["kalign"]
        text = "".join(f">p{i + 1}\n{row}\n" for i, row in enumerate(other))
        (directory / "MSASol1.fasta").write_text(text)

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        assert any(expander.label == "Knee or medoid?" for expander in app.expander)
        compared = next(
            frame.value for frame in app.dataframe if "agreement with the front" in frame.value
        )
        assert list(compared["alignment"]) == ["knee", "medoid"]
        assert list(compared["file"]) == ["MSASol2.fasta", "MSASol0.fasta"]
        assert any(button.label == "Show the medoid" for button in app.button)

    def test_should_add_the_gpcrdb_consistency_once_fetched(self, configured, data_root: Path):
        # Arrange: as above, with the numbering of every receptor kept
        from test_generic_numbers import ANSWERS, answer

        from transept import generic_numbers

        directory = write_finished_run(settings.runs_root(), data_root)
        (directory / "FUN.csv").write_text("30.0,0.50\n25.0,0.60\n28.0,0.58\n")
        other = ALIGNMENTS["kalign"]
        text = "".join(f">p{i + 1}\n{row}\n" for i, row in enumerate(other))
        (directory / "MSASol1.fasta").write_text(text)
        cache = generic_numbers.cache_directory()
        cache.mkdir(parents=True)
        for protein in datasets.read_topology(datasets.topology_file(data_root, "toy")):
            content = answer(protein, ANSWERS[protein.id])
            (cache / f"{protein.id}.json").write_text(json.dumps(content))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        compared = next(
            frame.value for frame in app.dataframe if "agreement with the front" in frame.value
        )
        assert "GPCRdb consistency" in compared.columns
        assert compared["GPCRdb consistency"].between(0, 1).all()


class TestResultsGpcrdb:
    def test_should_ask_before_going_to_gpcrdb(self, configured, data_root: Path):
        write_finished_run(settings.runs_root(), data_root)
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))
        assert not app.exception
        assert "has not been fetched from GPCRdb yet" in texts(app)
        assert any(button.label == "Get the GPCRdb numbering" for button in app.button)

    def test_should_show_the_numbering_kept(self, configured, data_root: Path, tmp_path: Path):
        # Arrange: the answers of GPCRdb, kept from an earlier request
        from test_generic_numbers import ANSWERS, answer

        from transept import generic_numbers

        write_finished_run(settings.runs_root(), data_root)
        topology = datasets.read_topology(datasets.topology_file(data_root, "toy"))
        directory = generic_numbers.cache_directory()
        directory.mkdir(parents=True)
        for protein in topology:
            content = answer(protein, ANSWERS[protein.id])
            (directory / f"{protein.id}.json").write_text(json.dumps(content))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        metric = next(m for m in app.metric if m.label.startswith("Helix residues"))
        assert metric.value == "93.3%"
        assert "The most conserved position of every helix (x.50)" in texts(app)


class TestResultsTools:
    @pytest.fixture
    def finished(self, configured, data_root: Path) -> AppTest:
        root = settings.runs_root()
        write_finished_run(root, data_root)
        from transept import baselines

        cache = baselines.cache_file(root, str(data_root), "toy", "VERIFIED", configured.jar)
        cache.parent.mkdir(parents=True)
        cache.write_text(
            "dataset,method,SOPwTP,lDDT,file,status,message\n"
            'toy,mafft,26.0,0.55,f,ok,""\n'
            'toy,kalign,32.0,0.40,f,ok,""\n'
            'toy,caretta,10.0,0.70,f,ok,""\n'
        )
        return open_page(ui.RESULTS, selected_run=("toy", "done"))

    def test_should_compare_the_selected_alignment_with_the_seeds_of_the_run(self, finished):
        # Assert: only the seeds of the run (mafft, kalign), not every precomputed alignment
        assert not finished.exception
        seeds = finished.dataframe[1].value
        assert sorted(seeds["method"]) == ["kalign", "mafft"]
        assert "against the seed alignments" in "\n".join(h.value for h in finished.subheader)

    def test_should_show_the_compromise_chosen_with_the_weight(self, finished):
        # Act: all the weight on SOPwTP selects the best SOPwTP solution (row 0)
        finished.slider(key="weight:toy / done").set_value(1.0).run()
        next(b for b in finished.button if b.label == "Show the compromise").click().run()

        # Assert
        assert finished.session_state["row:toy / done"] == 0

    def test_should_show_the_internal_seeds_that_the_run_used(self, configured, data_root: Path):
        # Arrange: a run seeded with internal seeds, which it saved in its own folder
        from transept import baselines

        root = settings.runs_root()
        directory = write_finished_run(root, data_root)
        config = json.loads((directory / "config.json").read_text())
        config["seedMethods"] = ["internal"]
        (directory / "config.json").write_text(json.dumps(config))
        seed = directory / "seeds" / "biojava-g20x2.fasta"
        seed.parent.mkdir()
        seed.write_text((directory / "MSASol0.fasta").read_text())
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["seeds"] = [
            {"method": "internal:biojava-g20x2", "file": str(seed), "sha256": "s1"}
        ]
        (directory / "metadata.json").write_text(json.dumps(metadata))
        cache = baselines.internal_cache_file(
            root, str(data_root), "toy", "VERIFIED", configured.jar, metadata
        )
        cache.parent.mkdir(parents=True)
        cache.write_text(
            'dataset,method,SOPwTP,lDDT,file,status,message\ntoy,biojava-g20x2,26.0,0.55,f,ok,""\n'
        )

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert: the seed is compared with the selected alignment, and drawn in the chart
        assert not app.exception
        seeds = app.dataframe[1].value
        assert list(seeds["method"]) == ["internal:biojava-g20x2"]

    def test_should_colour_the_alignment_by_what_biologists_ask(self, finished):
        # Assert: the colourings offered, with the support of the other alignments of the run
        colour = next(c for c in finished.get("button_group") if "Topology" in str(c.proto))
        assert "Support" in str(colour.proto)
        assert "Conservation" in str(colour.proto)

        # Act
        finished.session_state["colour_by:toy / done"] = "Conservation"
        finished.run()

        # Assert
        assert not finished.exception
        assert "**Conservation**: one minus the normalised entropy" in texts(finished)
        assert "How to read the tracks" in [item.label for item in finished.expander]

    def test_should_show_or_hide_the_seeds_in_the_chart(self, finished):
        def seed_traces(app) -> int:
            return sum(
                trace.get("name") == "Seed alignments"
                for chart in app.get("plotly_chart")
                for trace in json.loads(chart.proto.spec)["data"]
            )

        # Assert: shown by default
        assert seed_traces(finished) == 1

        # Act
        finished.toggle(key="show_seeds:toy / done").set_value(False).run()

        # Assert
        assert not finished.exception
        assert seed_traces(finished) == 0

    def test_should_offer_the_downloads_and_the_navigation(self, finished):
        labels = [button.label for button in finished.button]
        assert "Start" in labels
        downloads = [element.proto.label for element in finished.get("download_button")]
        assert any("Stockholm" in label for label in downloads)
        assert any("zip" in label for label in downloads)


class TestHistoryTrash:
    def test_should_list_and_restore_trashed_runs(self, configured, data_root: Path):
        # Arrange
        from transept import runs

        root = settings.runs_root()
        write_finished_run(root, data_root)
        runs.move_to_trash(root, runs.run_of(root, "toy", "done"))

        # Act
        app = open_page(ui.HISTORY)
        assert "no runs yet" in texts(app)
        next(button for button in app.button if button.label == "Restore").click().run()

        # Assert
        assert not app.exception
        assert sorted(app.dataframe[0].value["run"]) == ["done"]

    def test_should_empty_the_trash_after_confirmation(self, configured, data_root: Path):
        # Arrange
        from transept import runs

        root = settings.runs_root()
        write_finished_run(root, data_root)
        runs.move_to_trash(root, runs.run_of(root, "toy", "done"))
        app = open_page(ui.HISTORY)

        # Act
        app.button(key="ask_empty").click().run()
        app.button(key="confirm_empty_yes").click().run()

        # Assert
        assert runs.list_trash(root) == []


class TestResultsTabs:
    def test_should_summarise_and_compare_the_selected_alignment(self, configured, data_root):
        # Arrange: the run used mafft and kalign as seeds
        write_finished_run(settings.runs_root(), data_root)

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        assert [tab.label for tab in app.tabs] == [
            "Alignment",
            "Per protein",
            "Per helix",
            "GPCRdb",
            "Compare",
            "3D",
        ]
        labels = {metric.label: metric.value for metric in app.metric}
        assert labels["Shared residue pairs"] == "100.0%"  # the toy solutions repeat mafft
        compare = next(box for box in app.selectbox if box.label.startswith("Compare"))
        compare.set_value("seed: kalign").run()
        labels = {metric.label: metric.value for metric in app.metric}
        assert labels["Shared residue pairs"] != "100.0%"


class TestOldRuns:
    def test_should_not_mix_seeds_with_a_run_of_the_original_aggregation(
        self, configured, data_root: Path
    ):
        # Arrange: a run written by an earlier version of the tool
        import json

        directory = write_finished_run(settings.runs_root(), data_root)
        config = json.loads((directory / "config.json").read_text())
        config["lddtAggregation"] = "HARMONIC_OVER_LENGTH"
        (directory / "config.json").write_text(json.dumps(config))

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        assert "original lDDT aggregation" in texts(app)
