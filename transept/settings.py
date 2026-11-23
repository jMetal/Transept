"""Where Transept keeps its settings and runs, and where the core jar and the data are."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

HOME_VARIABLE = "TRANSEPT_HOME"
JAR_VARIABLE = "TRANSEPT_CORE_JAR"
JAR_NAME = "transept-core-0.1.0-jar-with-dependencies.jar"
SETTINGS_FILE_NAME = "settings.json"
REPOSITORY = Path(__file__).resolve().parent.parent
EXAMPLES = REPOSITORY / "examples" / "GPCRdb"
EXAMPLES_NAME = "Examples"
MY_DATASETS_NAME = "My datasets"
BENCHMARK_FOLDER = "GPCRdb"


def transept_home() -> Path:
    """Returns the directory of Transept: the repository, or TRANSEPT_HOME if it is set."""
    override = os.environ.get(HOME_VARIABLE)
    return Path(override) if override else REPOSITORY


def datasets_root() -> Path:
    """Returns the repository of the datasets added in Transept."""
    return transept_home() / "datasets"


def staging_root() -> Path:
    """Returns where a dataset is laid out and checked before it joins the repository."""
    return transept_home() / ".staging"


def runs_root() -> Path:
    """Returns the root of the runs: the tool writes to runs/ejecuciones/<dataset>/<run-id>/."""
    return transept_home() / "runs"


@dataclass(slots=True, frozen=True)
class Repository:
    """A directory of datasets, with the layout of GPCRdb.

    Attributes:
        name: Its name in the interface.
        path: The directory: the GPCRdb folder of the benchmark dataset, or your own.
    """

    name: str
    path: str


@dataclass(slots=True)
class Settings:
    """Paths Transept needs.

    Attributes:
        jar: The Transept core jar with dependencies.
        repositories: The repositories the user added; the examples are always available too.
        expert_mode: Whether every algorithm and formulation is offered, or only the recommended
            ones.
    """

    jar: str
    repositories: list[Repository] = field(default_factory=list)
    expert_mode: bool = False


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
    """The jar found by default_jar and no repository besides the examples."""
    return Settings(jar=default_jar())


def settings_file() -> Path:
    """Returns the file where the settings are saved."""
    return transept_home() / SETTINGS_FILE_NAME


def is_repository(path: Path | str) -> bool:
    """Tells whether a directory has the layout of a repository of datasets."""
    return (Path(path) / "sequences" / "tmregions").is_dir()


def all_repositories(settings: Settings) -> list[Repository]:
    """Returns the examples, the datasets added in Transept, if any, and the other repositories."""
    built_in = [Repository(EXAMPLES_NAME, str(EXAMPLES))]
    if is_repository(datasets_root()):
        built_in.append(Repository(MY_DATASETS_NAME, str(datasets_root())))
    return [*built_in, *settings.repositories]


def is_built_in(repository: Repository) -> bool:
    """Tells whether a repository belongs to Transept, so that it cannot be removed."""
    return repository.name in (EXAMPLES_NAME, MY_DATASETS_NAME)


def default_repository_name(path: Path | str) -> str:
    """Names a repository after its folder, or after the parent of a folder called GPCRdb."""
    directory = Path(path)
    return directory.parent.name if directory.name == BENCHMARK_FOLDER else directory.name


def add_repository(settings: Settings, path: str, name: str = "") -> Settings:
    """Returns the settings with one more repository.

    Raises:
        ValueError: If the directory is not a repository, or its path or name is already in use.
    """
    path = path.strip()
    if not path:
        raise ValueError("Enter the path of a directory.")
    directory = Path(path).expanduser()
    if not is_repository(directory):
        raise ValueError(
            f"{path} does not look like a data directory: it has no sequences/tmregions/ folder."
        )
    name = name.strip() or default_repository_name(directory)
    if name in (EXAMPLES_NAME, MY_DATASETS_NAME):
        raise ValueError(f"{name} is the name of a repository of Transept: choose another name.")
    for existing in all_repositories(settings):
        if Path(existing.path).resolve() == directory.resolve():
            raise ValueError(f"This directory is already the repository {existing.name}.")
        if existing.name == name:
            raise ValueError(f"There is already a repository called {name}: choose another name.")
    added = Repository(name, str(directory))
    return replace(settings, repositories=[*settings.repositories, added])


def remove_repository(settings: Settings, path: str) -> Settings:
    """Returns the settings without a repository; its files are not touched."""
    kept = [repository for repository in settings.repositories if repository.path != path]
    return replace(settings, repositories=kept)


def _saved_repositories(saved: dict) -> list[Repository]:
    """The repositories of a settings file; `data_root`, of earlier versions, becomes one."""
    repositories = [
        Repository(entry["name"], entry["path"]) for entry in saved.get("repositories", [])
    ]
    earlier = saved.get("data_root")
    if earlier and Path(earlier).resolve() != EXAMPLES.resolve():
        known = [Path(repository.path).resolve() for repository in repositories]
        if Path(earlier).resolve() not in known:
            repositories.append(Repository(default_repository_name(earlier), earlier))
    return repositories


def load_settings() -> Settings:
    """Loads the saved settings, or the defaults if there are none."""
    path = settings_file()
    if path.is_file():
        saved = json.loads(path.read_text(encoding="utf-8"))
        return Settings(
            saved.get("jar") or default_jar(),
            _saved_repositories(saved),
            bool(saved.get("expert_mode", False)),
        )
    return default_settings()


def save_settings(settings: Settings) -> None:
    """Saves the settings."""
    settings_file().write_text(json.dumps(asdict(settings), indent=2) + "\n", encoding="utf-8")


def java_command() -> str:
    """Returns the Java executable: $JAVA_HOME/bin/java if it exists, else java on the PATH.

    The Java of the Conda environment sets JAVA_HOME but is not on the PATH.
    """
    home = os.environ.get("JAVA_HOME")
    if home:
        candidate = Path(home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("java") or "java"


def java_version() -> str | None:
    """Returns the first line of `java -version`, or None if Java is not available."""
    java = java_command()
    if shutil.which(java) is None:
        return None
    result = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=30)
    lines = (result.stderr or result.stdout).strip().splitlines()
    return lines[0] if lines else "java"


def problems(settings: Settings) -> list[str]:
    """Lists what prevents running the tool with these settings; empty if nothing does."""
    found = []
    if java_version() is None:
        found.append(
            "Java was not found (neither in JAVA_HOME nor on the PATH): run `make setup`, or "
            "install Java 21 or newer."
        )
    if not Path(settings.jar).is_file():
        found.append(
            f"The jar was not found at {settings.jar}. Clone Transept-core next to this "
            "repository and run `make setup`, or run `make setup JAR=<path to the jar>`, or set "
            "its path below."
        )
    if not any(is_repository(repository.path) for repository in all_repositories(settings)):
        found.append(
            "No data directory is available: add one in Explore > Datasets, for example the "
            "GPCRdb folder of the benchmark dataset."
        )
    return found


def data_root_of_run(settings: Settings, recorded: str | None, dataset: str) -> str:
    """Returns the data directory of a run: the one it recorded, if it still exists.

    Otherwise, the first repository with a dataset of that name, or an empty string if none has it.
    """
    if recorded and is_repository(recorded):
        return recorded
    for repository in all_repositories(settings):
        topology = Path(repository.path) / "sequences" / "tmregions"
        if (topology / f"{dataset}_predicted_topologies.3line").is_file():
            return repository.path
    return recorded or ""
