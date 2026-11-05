"""Where Transept keeps its settings and runs, and where the core jar and the data are."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

STUDIO_HOME_VARIABLE = "TRANSEPT_HOME"
JAR_VARIABLE = "TRANSEPT_CORE_JAR"
JAR_NAME = "transept-core-0.1.0-jar-with-dependencies.jar"
SETTINGS_FILE_NAME = "settings.json"
REPOSITORY = Path(__file__).resolve().parent.parent
EXAMPLES = REPOSITORY / "examples" / "GPCRdb"


def studio_home() -> Path:
    """Returns the directory of Transept: the repository, or TRANSEPT_HOME if it is set."""
    override = os.environ.get(STUDIO_HOME_VARIABLE)
    return Path(override) if override else REPOSITORY


def runs_root() -> Path:
    """Returns the root of the runs: the tool writes to runs/ejecuciones/<dataset>/<run-id>/."""
    return studio_home() / "runs"


@dataclass(slots=True)
class Settings:
    """Paths Transept needs.

    Attributes:
        jar: The Transept core jar with dependencies.
        data_root: A data directory with the layout of GPCRdb (the examples of this repository,
            the GPCRdb folder of the benchmark dataset, or your own).
    """

    jar: str
    data_root: str


def jar_candidates() -> list[Path]:
    """Places where the jar is looked for, in order: lib/ and a sibling Transept core build."""
    parent = REPOSITORY.parent
    return [
        REPOSITORY / "lib" / JAR_NAME,
        parent / "transept-core" / "target" / JAR_NAME,
        parent / "Transept-core" / "target" / JAR_NAME,
    ]


def default_jar() -> str:
    """TRANSEPT_CORE_JAR if it is set, else the first candidate that exists, else lib/."""
    override = os.environ.get(JAR_VARIABLE)
    if override:
        return override
    for candidate in jar_candidates():
        if candidate.is_file():
            return str(candidate)
    return str(jar_candidates()[0])


def default_settings() -> Settings:
    """The jar found by default_jar and the examples of this repository."""
    return Settings(jar=default_jar(), data_root=str(EXAMPLES))


def settings_file() -> Path:
    """Returns the file where the settings are saved."""
    return studio_home() / SETTINGS_FILE_NAME


def load_settings() -> Settings:
    """Loads the saved settings, or the defaults if there are none."""
    path = settings_file()
    if path.is_file():
        saved = json.loads(path.read_text(encoding="utf-8"))
        defaults = asdict(default_settings())
        return Settings(**{key: saved.get(key) or value for key, value in defaults.items()})
    return default_settings()


def save_settings(settings: Settings) -> None:
    """Saves the settings."""
    settings_file().write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")


def java_version() -> str | None:
    """Returns the first line of `java -version`, or None if Java is not on the PATH."""
    if shutil.which("java") is None:
        return None
    result = subprocess.run(["java", "-version"], capture_output=True, text=True, timeout=30)
    lines = (result.stderr or result.stdout).strip().splitlines()
    return lines[0] if lines else "java"


def problems(settings: Settings) -> list[str]:
    """Lists what prevents running the tool with these settings; empty if nothing does."""
    found = []
    if java_version() is None:
        found.append("Java was not found on the PATH: install Java 21 or newer.")
    if not Path(settings.jar).is_file():
        found.append(
            f"The jar was not found at {settings.jar}. Run `make setup JAR=<path to the jar>`, "
            "or build it with `mvn clean package -DskipTests` in a clone of Transept-core next "
            "to this repository, or set its path below."
        )
    if not (Path(settings.data_root) / "sequences" / "tmregions").is_dir():
        found.append(
            f"{settings.data_root} does not look like a data directory: it has no "
            "sequences/tmregions/ folder."
        )
    return found
