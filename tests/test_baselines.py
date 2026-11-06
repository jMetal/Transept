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
