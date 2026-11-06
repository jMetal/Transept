"""The checklist of a dataset: what it holds and whether it can be used."""

from pathlib import Path

from transept import dataset_check, datasets, settings
from transept.dataset_check import Level, Status


def level_of(report: dataset_check.DatasetReport, name: str) -> Level:
    return next(check.level for check in report.checks if check.name == name)


def write_structures(root: Path, proteins: tuple[str, ...] = ("p1", "p2", "p3")) -> None:
    for protein in proteins:
        (root / "distances" / "toy" / f"{protein}_D.csv").write_text("0\n")
        (root / "distances" / "toy" / f"{protein}_idx.csv").write_text("1\n")
        models = root / "alphafold_pdb" / "toy"
        models.mkdir(parents=True, exist_ok=True)
        (models / f"{protein}.pdb").write_text("ATOM\n")


def remove_invalid_seeds(root: Path) -> None:
    (root / "precomputed" / "toy" / "broken_toy.fasta").unlink()


class TestCheckDataset:
    def test_should_be_ready_when_everything_is_in_place(self, data_root: Path):
        # Arrange
        write_structures(data_root)
        remove_invalid_seeds(data_root)
        reference = datasets.reference_file(data_root, "toy")
        reference.parent.mkdir(parents=True)
        reference.write_text(">p1\nA\n")

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.READY
        assert report.reference
        assert report.structures == len(report.proteins) == 3
        assert all(check.level == Level.OK for check in report.checks)

    def test_should_warn_about_a_protein_without_structure(self, data_root: Path):
        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.WARNINGS
        assert report.structures == 2
        assert level_of(report, "Structures") == Level.WARNING
        assert not next(p for p in report.proteins if p.id == "p3").structure

    def test_should_warn_about_an_invalid_seed_and_say_why(self, data_root: Path):
        # Arrange
        write_structures(data_root)

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.WARNINGS
        broken = next(seed for seed in report.seeds if seed.tool == "broken")
        assert "residue" in broken.problem
        assert report.valid_seeds == len(report.seeds) - 1

    def test_should_report_the_known_issues_of_a_seed(self, data_root: Path):
        report = dataset_check.check_dataset(data_root, "toy")
        caretta = next(seed for seed in report.seeds if seed.tool == "caretta")
        assert caretta.known_issue == datasets.KNOWN_ISSUES["caretta"]

    def test_should_not_warn_without_a_reference_or_a_model(self, data_root: Path):
        # Arrange: distances, but no models and no reference
        for protein in ("p3",):
            (data_root / "distances" / "toy" / f"{protein}_D.csv").write_text("0\n")
            (data_root / "distances" / "toy" / f"{protein}_idx.csv").write_text("1\n")
        remove_invalid_seeds(data_root)

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.READY
        assert level_of(report, "Reference alignment") == Level.INFO
        assert level_of(report, "Structure models") == Level.INFO

    def test_should_not_be_usable_without_any_structure(self, data_root: Path):
        # Arrange
        for path in (data_root / "distances" / "toy").iterdir():
            path.unlink()

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.NOT_USABLE
        assert level_of(report, "Structures") == Level.ERROR

    def test_should_not_fail_on_a_broken_topology(self, data_root: Path):
        # Arrange
        datasets.topology_file(data_root, "toy").write_text(">p1\nAC\n")

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.NOT_USABLE
        assert report.proteins == ()
        assert report.seeds == ()
        assert "three lines per protein" in report.checks[0].message

    def test_should_not_be_usable_with_a_single_protein(self, data_root: Path):
        # Arrange
        datasets.topology_file(data_root, "toy").write_text(">p1\nAC\nMM\n")

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert report.status == Status.NOT_USABLE
        assert "at least 2 proteins" in report.checks[0].message

    def test_should_count_the_helices_and_the_lengths(self, data_root: Path):
        # Arrange
        datasets.topology_file(data_root, "toy").write_text(">p1\nACDEFG\nMMOOMM\n>p2\nAC\nOO\n")

        # Act
        report = dataset_check.check_dataset(data_root, "toy")

        # Assert
        assert [protein.helices for protein in report.proteins] == [2, 0]
        assert report.mean_length == 4
        assert report.max_length == 6


class TestCatalogue:
    def test_should_keep_datasets_with_the_same_name_apart(self, data_root: Path, tmp_path: Path):
        # Arrange
        twin = tmp_path / "Twin"
        (twin / "sequences" / "tmregions").mkdir(parents=True)
        (twin / "sequences" / "tmregions" / "toy_predicted_topologies.3line").write_text(
            datasets.topology_file(data_root, "toy").read_text()
        )
        repositories = [
            settings.Repository("One", str(data_root)),
            settings.Repository("Two", str(twin)),
            settings.Repository("Gone", str(tmp_path / "gone")),
        ]

        # Act
        entries = dataset_check.catalogue(repositories)

        # Assert
        assert [(entry.repository.name, entry.name) for entry in entries] == [
            ("One", "toy"),
            ("Two", "toy"),
        ]
        assert entries[0].report.structures == 2
        assert entries[1].report.status == Status.NOT_USABLE
