"""The pages open without errors and show what they should, without a browser."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import ALIVE_PID, write_finished_run, write_job
from streamlit.testing.v1 import AppTest

from transept import options, settings, ui
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
        assert app.title[0].value == "Transept"
        assert "jar was not found" in texts(app)

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
        shown = texts(app)
        for section in SECTIONS:
            assert section.name.upper() in shown
            for page in section.pages:
                assert page.title in shown
                assert page.description in shown

    def test_should_link_only_the_available_pages(self, configured):
        # Arrange
        pages = [page for section in SECTIONS for page in section.pages]

        # Act
        app = open_page(ui.HOME)

        # Assert
        assert not app.exception
        labels = [link.proto.label for link in app.get("page_link")]
        links = {label for label in labels if label.startswith("Open ")}
        assert links == {f"Open {page.title}" for page in pages if page.available}
        assert texts(app).count("Coming soon") == sum(not page.available for page in pages)


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

    def test_should_add_a_repository_and_refuse_a_wrong_directory(
        self, configured, tmp_path: Path
    ):
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

    def test_should_show_a_three_objective_run(self, configured, data_root: Path):
        # Arrange
        directory = write_finished_run(settings.runs_root(), data_root)
        metadata = json.loads((directory / "metadata.json").read_text())
        metadata["objectives"] = ["SOPwTP", "lDDT", "coverage"]
        (directory / "metadata.json").write_text(json.dumps(metadata))
        (directory / "FUN.csv").write_text("30,0.5,0.9\n25,0.6,0.8\n30,0.5,0.9\n20,0.55,0.95\n")

        # Act
        app = open_page(ui.RESULTS, selected_run=("toy", "done"))

        # Assert
        assert not app.exception
        assert "no front chart yet" in texts(app)
        assert not app.get("plotly_chart") or all(
            "Pareto" not in str(chart.proto) for chart in app.get("plotly_chart")
        )

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
            "Compare",
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
