import sys
from pathlib import Path

from transept import baselines, settings

CSV = (
    "dataset,method,SOPwTP,lDDT,file,status,message\n"
    '"toy","mafft",30.0,0.5,"f",ok,""\n'
    '"toy","broken",,,"f",failed,"bad"\n'
)


def test_should_build_the_baseline_command(tmp_path: Path):
    arguments = baselines.command("/t.jar", "/data", "toy", "VERIFIED", tmp_path / "o")
    assert arguments[:4] == [settings.java_command(), "-jar", "/t.jar", "baseline"]
    assert "VERIFIED" in arguments and "toy" in arguments


def test_should_score_once_and_keep_only_valid_seeds(tmp_path: Path, monkeypatch):
    # Arrange: replace the tool by a script that writes the CSV and counts its calls
    calls = tmp_path / "calls"

    def fake(jar, data_root, dataset, policy, output):
        script = f"open({str(calls)!r}, 'a').write('x'); open({str(output)!r}, 'w').write({CSV!r})"
        return [sys.executable, "-c", script]

    monkeypatch.setattr(baselines, "command", fake)

    # Act
    first = baselines.seed_scores("/t.jar", "/data", "toy", tmp_path)
    second = baselines.seed_scores("/t.jar", "/data", "toy", tmp_path)

    # Assert
    assert list(first["method"]) == ["mafft"]
    assert first.equals(second)
    assert calls.read_text() == "x"


def test_should_return_nothing_if_the_tool_fails(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        baselines, "command", lambda *args: [sys.executable, "-c", "raise SystemExit(1)"]
    )
    assert baselines.seed_scores("/t.jar", "/data", "toy", tmp_path).empty


def test_should_cache_per_build_of_the_tool(tmp_path: Path):
    # Arrange
    jar = tmp_path / "tool.jar"
    jar.write_text("first build")
    first = baselines.cache_file(tmp_path, "/data", "toy", "VERIFIED", str(jar))

    # Act: another build of the tool
    jar.write_text("second build, longer")
    second = baselines.cache_file(tmp_path, "/data", "toy", "VERIFIED", str(jar))

    # Assert
    assert first != second
    assert first.name.startswith("toy-VERIFIED-")


def test_should_cache_per_data_directory(tmp_path: Path):
    # Act
    first = baselines.cache_file(tmp_path, "/one", "toy", "VERIFIED", "/t.jar")
    second = baselines.cache_file(tmp_path, "/two", "toy", "VERIFIED", "/t.jar")

    # Assert
    assert first != second


def internal_metadata(tmp_path: Path) -> dict:
    seed = tmp_path / "seeds" / "biojava-g20x2.fasta"
    seed.parent.mkdir()
    seed.write_text(">p1\nACD\n")
    return {
        "seeds": [
            {"method": "mafft", "file": str(tmp_path / "mafft.fasta"), "sha256": "a"},
            {"method": "internal:biojava-g20x2", "file": str(seed), "sha256": "b"},
            {"method": "internal:gone", "file": str(tmp_path / "gone.fasta"), "sha256": "c"},
        ]
    }


def test_should_find_the_internal_seeds_that_still_exist(tmp_path: Path):
    files = baselines.internal_seed_files(internal_metadata(tmp_path))
    assert [file.name for file in files] == ["biojava-g20x2.fasta"]


def test_should_score_the_internal_seeds_of_a_run_once(tmp_path: Path, monkeypatch):
    # Arrange: a tool that records its arguments and writes the CSV
    calls = tmp_path / "calls"
    csv = (
        'dataset,method,SOPwTP,lDDT,file,status,message\n"toy","biojava-g20x2",31.0,0.6,"f",ok,""\n'
    )

    def fake(jar, data_root, dataset, policy, output):
        script = (
            f"import sys; open({str(calls)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n'); "
            f"open({str(output)!r}, 'w').write({csv!r})"
        )
        return [sys.executable, "-c", script]

    monkeypatch.setattr(baselines, "command", fake)
    metadata = internal_metadata(tmp_path)

    # Act
    first = baselines.internal_seed_scores("/t.jar", "/data", "toy", metadata, tmp_path)
    second = baselines.internal_seed_scores("/t.jar", "/data", "toy", metadata, tmp_path)

    # Assert: only the existing internal seed is passed, and the result is cached
    assert list(first["method"]) == ["internal:biojava-g20x2"]
    assert first.equals(second)
    recorded = calls.read_text().splitlines()
    assert len(recorded) == 1
    assert recorded[0].startswith("--alignments ")
    assert recorded[0].endswith("biojava-g20x2.fasta")


def test_should_not_call_the_tool_without_internal_seeds(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(baselines, "command", lambda *args: ["/nonexistent"])
    metadata = {"seeds": [{"method": "mafft", "file": "/x.fasta", "sha256": "a"}]}
    assert baselines.internal_seed_scores("/t.jar", "/data", "toy", metadata, tmp_path).empty
