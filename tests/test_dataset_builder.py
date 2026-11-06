"""A dataset from the files of the user: laid out, checked, and only then added."""

from pathlib import Path

import pytest
from conftest import THREE_LINE, pdb_text

from transept import dataset_builder, datasets
from transept.dataset_builder import DatasetBuildError, DatasetFiles, Source
from transept.dataset_check import Status

TOPOLOGY = Source("anything.3line", THREE_LINE.encode())
P1 = Source("p1.pdb", pdb_text(3).encode())
P2 = Source("p2.pdb", pdb_text(4).encode())
SEED = ">p1\nACD-\n>p2\nACDE\n"


def stage(tmp_path: Path, **files) -> dataset_builder.StagedDataset:
    return dataset_builder.stage(
        DatasetFiles("mine", TOPOLOGY, **files), tmp_path / "staging", tmp_path / "repo"
    )


class TestStage:
    def test_should_lay_out_a_dataset_and_compute_its_distances(self, tmp_path: Path):
        # Act
        staged = stage(
            tmp_path,
            structures=(P1, P2),
            seeds=(Source("mafft_mine.fasta", SEED.encode()),),
            reference=Source("gpcrdb.fasta", SEED.encode()),
        )

        # Assert
        assert staged.report.status == Status.READY
        assert staged.report.structures == 2
        assert [seed.tool for seed in staged.report.seeds] == ["mafft"]
        assert staged.report.reference
        assert any("Distances computed" in note for note in staged.notes)
        assert not (tmp_path / "repo").exists()

    def test_should_not_compute_the_distances_it_was_given(self, tmp_path: Path):
        # Arrange
        given = (
            P1,
            Source("p1_D.csv", b"9,9\n9,9\n"),
            Source("p1_idx.csv", b"1\n2\n"),
            P2,
        )

        # Act
        staged = stage(tmp_path, structures=given)

        # Assert
        matrix = staged.root / "distances" / "mine" / "p1_D.csv"
        assert matrix.read_text() == "9,9\n9,9\n"
        assert "1 protein(s)" in next(n for n in staged.notes if "Distances computed" in n)

    def test_should_match_the_files_regardless_of_the_case(self, tmp_path: Path):
        # Act
        staged = stage(tmp_path, structures=(Source("P1.pdb", pdb_text(3).encode()), P2))

        # Assert
        assert datasets.structure_model_file(staged.root, "mine", "p1").is_file()
        assert staged.report.structures == 2

    def test_should_report_the_files_that_match_no_protein(self, tmp_path: Path):
        # Act
        staged = stage(tmp_path, structures=(P1, Source("AF-P1-F1.pdb", pdb_text(3).encode())))

        # Assert
        assert staged.report.status == Status.WARNINGS
        assert any("AF-P1-F1.pdb" in note for note in staged.notes)

    def test_should_report_a_structure_it_cannot_read(self, tmp_path: Path):
        # Act
        staged = stage(tmp_path, structures=(P1, Source("p2.pdb", b"not a structure\n")))

        # Assert
        assert staged.report.structures == 1
        assert any("The structure of p2 was not used" in note for note in staged.notes)
        assert not datasets.structure_model_file(staged.root, "mine", "p2").exists()

    def test_should_not_write_outside_the_dataset(self, tmp_path: Path):
        # Act: file names as a browser could send them
        staged = stage(
            tmp_path,
            structures=(P1, Source("../../p2.pdb", pdb_text(4).encode())),
            seeds=(Source("../../evil.fasta", SEED.encode()),),
        )

        # Assert
        assert datasets.structure_model_file(staged.root, "mine", "p2").is_file()
        assert datasets.seed_file(staged.root, "mine", "evil").is_file()
        assert sorted(path.name for path in tmp_path.iterdir()) == ["staging"]

    @pytest.mark.parametrize("identifier", ["a/b", "..", "a\\b"])
    def test_should_refuse_an_identifier_that_cannot_name_a_file(self, tmp_path, identifier):
        files = DatasetFiles("mine", Source("t", f">{identifier}\nAC\nMM\n>c\nAC\nMM\n".encode()))
        with pytest.raises(DatasetBuildError, match="cannot name a file"):
            dataset_builder.stage(files, tmp_path / "staging", tmp_path / "repo")

    def test_should_refuse_a_repeated_protein(self, tmp_path: Path):
        files = DatasetFiles("mine", Source("t", b">a\nAC\nMM\n>a\nAC\nMM\n"))
        with pytest.raises(DatasetBuildError, match="appears twice"):
            dataset_builder.stage(files, tmp_path / "staging", tmp_path / "repo")

    def test_should_not_fail_on_a_broken_topology(self, tmp_path: Path):
        # Act
        staged = dataset_builder.stage(
            DatasetFiles("mine", Source("t", b">a\nAC\n"), structures=(P1,)),
            tmp_path / "staging",
            tmp_path / "repo",
        )

        # Assert
        assert staged.report.status == Status.NOT_USABLE

    def test_should_keep_the_name_internal_for_transept(self, tmp_path: Path):
        with pytest.raises(DatasetBuildError, match="reserved"):
            stage(tmp_path, seeds=(Source("internal.fasta", SEED.encode()),))

    def test_should_discard_a_previous_attempt(self, tmp_path: Path):
        # Arrange
        stage(tmp_path, structures=(P1, P2))

        # Act
        staged = stage(tmp_path, structures=(P1,))

        # Assert
        assert staged.report.structures == 1


class TestName:
    @pytest.mark.parametrize("name", ["", "../x", "a b", ".hidden", "a/b"])
    def test_should_refuse_a_wrong_name(self, tmp_path: Path, name: str):
        with pytest.raises(DatasetBuildError, match="starts with a letter"):
            dataset_builder.check_name(name, tmp_path)

    def test_should_refuse_a_name_in_use(self, tmp_path: Path):
        topology = datasets.topology_file(tmp_path, "mine")
        topology.parent.mkdir(parents=True)
        topology.write_text(THREE_LINE)
        with pytest.raises(DatasetBuildError, match="already has"):
            dataset_builder.check_name("mine", tmp_path)


class TestPublish:
    def test_should_move_the_dataset_to_the_repository(self, tmp_path: Path):
        # Arrange
        staged = stage(tmp_path, structures=(P1, P2), seeds=(Source("mafft.fasta", SEED.encode()),))
        repository = tmp_path / "repo"

        # Act
        dataset_builder.publish(staged, repository)

        # Assert
        assert datasets.list_datasets(repository) == ["mine"]
        assert datasets.list_seed_tools(repository, "mine") == ["mafft"]
        assert (
            datasets.proteins_without_structure(
                repository,
                "mine",
                datasets.read_topology(datasets.topology_file(repository, "mine")),
            )
            == []
        )
        assert not staged.root.exists()

    def test_should_refuse_a_dataset_that_cannot_be_used(self, tmp_path: Path):
        staged = stage(tmp_path)
        with pytest.raises(DatasetBuildError, match="cannot be used"):
            dataset_builder.publish(staged, tmp_path / "repo")

    def test_should_not_overwrite_a_dataset(self, tmp_path: Path):
        # Arrange
        staged = stage(tmp_path, structures=(P1, P2))
        repository = tmp_path / "repo"
        topology = datasets.topology_file(repository, "mine")
        topology.parent.mkdir(parents=True)
        topology.write_text("kept\n")

        # Act & Assert
        with pytest.raises(DatasetBuildError, match="already has"):
            dataset_builder.publish(staged, repository)
        assert topology.read_text() == "kept\n"


class TestFolder:
    def test_should_take_the_structural_files_of_a_folder(self, tmp_path: Path):
        # Arrange
        (tmp_path / "p1.pdb").write_text(pdb_text(3))
        (tmp_path / "p1_D.csv").write_text("0\n")
        (tmp_path / "notes.txt").write_text("no")

        # Act
        sources = dataset_builder.structure_sources_in_folder(str(tmp_path))

        # Assert
        assert [source.name for source in sources] == ["p1.pdb", "p1_D.csv"]

    def test_should_refuse_a_folder_that_does_not_exist(self, tmp_path: Path):
        with pytest.raises(DatasetBuildError, match="does not exist"):
            dataset_builder.structure_sources_in_folder(str(tmp_path / "gone"))
