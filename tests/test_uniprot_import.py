"""Proteins from UniProt and AlphaFold DB, with their answers faked: the tests never go online."""

import json
import urllib.parse
from pathlib import Path

import pytest

from transept import uniprot_import

SEQUENCE = "MASEFKKKLFWRAVVAEF"  # 18 residues


def record(accession="P29972", name="AQP1_HUMAN", sequence=SEQUENCE, features=None) -> dict:
    """A UniProt search result, as the REST API returns it."""
    return {
        "primaryAccession": accession,
        "uniProtkbId": name,
        "proteinDescription": {"recommendedName": {"fullName": {"value": "Aquaporin-1"}}},
        "organism": {"scientificName": "Homo sapiens"},
        "sequence": {"value": sequence, "length": len(sequence)},
        "features": features
        if features is not None
        else [
            feature("Topological domain", 1, 3, "Cytoplasmic"),
            feature("Transmembrane", 4, 9, "Helical"),
            feature("Topological domain", 10, 11, "Extracellular"),
            feature("Intramembrane", 12, 15, ""),
            feature("Topological domain", 16, 18, "Cytoplasmic"),
        ],
    }


def feature(kind: str, start: int, end: int, description: str) -> dict:
    return {
        "type": kind,
        "location": {"start": {"value": start}, "end": {"value": end}},
        "description": description,
    }


@pytest.fixture
def web(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict:
    """Fake answers by URL fragment; records which URLs were asked for."""
    monkeypatch.setenv("TRANSEPT_HOME", str(tmp_path))
    answers: dict[str, bytes | None] = {}
    asked: list[str] = []

    def get(url: str) -> bytes | None:
        asked.append(url)
        for fragment, answer in answers.items():
            if fragment in urllib.parse.unquote(url):
                return answer
        return None

    monkeypatch.setattr(uniprot_import, "_get", get)
    answers["__asked__"] = asked  # type: ignore[assignment]
    return answers


def uniprot_answer(*records: dict) -> bytes:
    return json.dumps({"results": list(records)}).encode()


def alphafold_answer(accession: str, sequence: str = SEQUENCE) -> bytes:
    return json.dumps(
        [
            {
                "uniprotAccession": accession,
                "uniprotSequence": sequence,
                "pdbUrl": f"https://alphafold.example/AF-{accession}-F1-model_v6.pdb",
            }
        ]
    ).encode()


class TestParseIdentifiers:
    def test_should_split_by_spaces_commas_and_lines(self):
        assert uniprot_import.parse_identifiers("P29972, AQP2_HUMAN\nQ92482;P55064") == [
            "P29972",
            "AQP2_HUMAN",
            "Q92482",
            "P55064",
        ]

    def test_should_drop_repetitions_whatever_the_case(self):
        assert uniprot_import.parse_identifiers("P29972 p29972 P29972") == ["P29972"]


class TestTopology:
    def test_should_mark_transmembrane_and_intramembrane_segments(self):
        topology, segments = uniprot_import.topology_of(record())

        assert topology == "IIIMMMMMMOOMMMMIII"
        assert segments == 2

    def test_should_leave_unannotated_residues_outside(self):
        topology, segments = uniprot_import.topology_of(record(features=[]))

        assert topology == "O" * len(SEQUENCE)
        assert segments == 0

    def test_should_name_the_protein_after_its_entry_name_in_lower_case(self):
        entry = uniprot_import.entry_of(record())

        assert entry.name == "aqp1_human"
        assert entry.description == "Aquaporin-1, Homo sapiens"


class TestFetch:
    def test_should_get_the_proteins_and_their_models(self, web):
        # Arrange
        web["accession:P29972"] = uniprot_answer(record())
        web["id:AQP2_HUMAN"] = uniprot_answer(record("P41181", "AQP2_HUMAN"))
        web["prediction/P29972"] = alphafold_answer("P29972")
        web["prediction/P41181"] = alphafold_answer("P41181")
        web["AF-P29972"] = b"ATOM model 1\n"
        web["AF-P41181"] = b"ATOM model 2\n"

        # Act
        found = uniprot_import.fetch(["P29972", "AQP2_HUMAN"])

        # Assert
        assert [entry.name for entry in found.entries] == ["aqp1_human", "aqp2_human"]
        assert found.models["aqp2_human"].read_bytes() == b"ATOM model 2\n"
        assert found.problems == ()

    def test_should_ask_only_once(self, web):
        web["accession:P29972"] = uniprot_answer(record())
        web["prediction/P29972"] = alphafold_answer("P29972")
        web["AF-P29972"] = b"ATOM\n"
        uniprot_import.fetch(["P29972"])
        asked = len(web["__asked__"])

        uniprot_import.fetch(["P29972"])

        assert len(web["__asked__"]) == asked

    def test_should_report_what_cannot_be_used(self, web):
        # Arrange: an unknown identifier, a protein without topology, and a model of another
        # sequence (a fragment)
        web["accession:XXXX"] = uniprot_answer()
        web["accession:Q00001"] = uniprot_answer(record("Q00001", "NOTM_HUMAN", features=[]))
        web["accession:P29972"] = uniprot_answer(record())
        web["prediction/P29972"] = alphafold_answer("P29972", sequence="MASE")

        # Act
        found = uniprot_import.fetch(["XXXX", "Q00001", "P29972"])

        # Assert
        assert [entry.name for entry in found.entries] == ["aqp1_human"]
        assert found.models == {}
        problems = " ".join(found.problems)
        assert "XXXX: not found in UniProt" in problems
        assert "notm_human: UniProt has no transmembrane segment" in problems
        assert "not of the current UniProt sequence" in problems

    def test_should_refuse_identifiers_that_are_not_words(self, web):
        found = uniprot_import.fetch(["P29972&format=xml"])

        assert found.entries == ()
        assert web["__asked__"] == []


class TestSources:
    def test_should_write_a_three_line_file_and_name_the_models(self, web):
        web["accession:P29972"] = uniprot_answer(record())
        web["prediction/P29972"] = alphafold_answer("P29972")
        web["AF-P29972"] = b"ATOM\n"
        found = uniprot_import.fetch(["P29972"])

        topology, models = uniprot_import.sources(found)

        assert topology.data.decode() == (f">aqp1_human | P29972\n{SEQUENCE}\nIIIMMMMMMOOMMMMIII\n")
        assert [model.name for model in models] == ["aqp1_human.pdb"]
