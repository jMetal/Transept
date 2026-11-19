from pathlib import Path

import pytest

from transept import datasets


class TestListing:
    def test_should_list_the_datasets_with_a_topology_file(self, data_root: Path):
        assert datasets.list_datasets(data_root) == ["toy"]

    def test_should_list_no_datasets_in_a_directory_without_topologies(self, tmp_path: Path):
        assert datasets.list_datasets(tmp_path) == []

    def test_should_list_the_seed_tools_and_ignore_other_files(self, data_root: Path):
        assert datasets.list_seed_tools(data_root, "toy") == [
            "broken",
            "caretta",
            "kalign",
            "mafft",
        ]

    def test_should_list_no_seed_tools_of_an_unknown_dataset(self, data_root: Path):
        assert datasets.list_seed_tools(data_root, "other") == []

    def test_should_choose_the_default_seeds_among_the_available_ones(self):
        assert datasets.default_seed_tools(["caretta", "mafft", "kalign"]) == ["kalign", "mafft"]

    def test_should_recommend_the_sequence_and_structural_seeds_among_the_available_ones(self):
        available = ["broken", "usalign", "caretta", "mafft", "kalign"]

        assert datasets.recommended_seed_tools(available) == [
            "kalign",
            "mafft",
            "caretta",
            "usalign",
        ]

    def test_should_recommend_no_seeds_when_none_is_known(self):
        assert datasets.recommended_seed_tools(["broken", "internal"]) == []


class TestTopology:
    def test_should_read_identifiers_sequences_and_topologies(self, data_root: Path):
        # Act
        proteins = datasets.read_topology(datasets.topology_file(data_root, "toy"))

        # Assert
        assert [protein.id for protein in proteins] == ["p1", "p2", "p3"]
        assert proteins[0].residues == "ACDEFGHIK"
        assert proteins[0].topology == "OOMMMMOOO"

    def test_should_reject_a_topology_of_another_length(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "bad.3line"
        path.write_text(">p | x\nACD\nOM\n")

        # Act & Assert
        with pytest.raises(ValueError, match="differ in length"):
            datasets.read_topology(path)

    def test_should_reject_a_file_without_three_lines_per_protein(self, tmp_path: Path):
        # Arrange
        path = tmp_path / "bad.3line"
        path.write_text(">p | x\nACD\n")

        # Act & Assert
        with pytest.raises(ValueError, match="three lines"):
            datasets.read_topology(path)


class TestIdentifiers:
    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            (">FZD2_HUMAN description", "fzd2_human"),
            (">sp|P12345|NAME_HUMAN", "p12345"),
            (">fzd2_human|SP+TM", "fzd2_human"),
            (">fzd2_human:A", "fzd2_human"),
            (">fzd2_human.pdb", "fzd2_human"),
        ],
    )
    def test_should_normalise_headers_as_the_tool_does(self, header, expected):
        assert datasets.normalize_id(header) == expected


class TestSeeds:
    @pytest.fixture
    def proteins(self, data_root: Path):
        return datasets.read_topology(datasets.topology_file(data_root, "toy"))

    def write(self, tmp_path: Path, text: str) -> Path:
        path = tmp_path / "seed.fasta"
        path.write_text(text)
        return path

    def test_should_accept_a_valid_seed(self, data_root: Path, proteins):
        path = datasets.seed_file(data_root, "toy", "mafft")
        assert datasets.seed_problem(path, proteins) is None

    def test_should_report_the_first_wrong_residue(self, data_root: Path, proteins):
        path = datasets.seed_file(data_root, "toy", "broken")
        assert datasets.seed_problem(path, proteins) == "residue 8 of 'p2' is 'W' instead of 'K'"

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            (">p1\nACDEFGHIK\n>p2\nACDEGHIK-\n", "protein 'p3' is missing"),
            (">p1\nACDEFGHIK\n>p1\nACDEFGHIK\n", "appears twice"),
            (">p1\nACDEFGHIK\n>p2\nACDEGHIK\n>p3\nACEFGHIK-\n", "another aligned length"),
            (">p1\nACDEFGHIK\n>p2\nACDEGHI--\n>p3\nACEFGHIK-\n", "has 7 residues, expected 8"),
            (">p1\nACDEFGHIK\n>p2\nACDEGHIK-\n>p3\nACEFGHIK-\n>p9\nA\n", "unexpected proteins: p9"),
            ("ACD\n>p1\nACD\n", "unreadable"),
        ],
    )
    def test_should_explain_why_the_tool_would_reject_a_seed(
        self, tmp_path: Path, proteins, text, message
    ):
        assert message in datasets.seed_problem(self.write(tmp_path, text), proteins)

    def test_should_accept_dots_lowercase_and_uniprot_headers(self, tmp_path: Path, proteins):
        text = ">P1 x\nacdefghik\n>p2:A\nACDEGHIK.\n>p3.pdb\nACEFGHIK-\n"
        assert datasets.seed_problem(self.write(tmp_path, text), proteins) is None

    def test_should_list_the_proteins_without_structure(self, data_root: Path, proteins):
        assert datasets.proteins_without_structure(data_root, "toy", proteins) == ["p3"]
