# AGENTS.md

Guidance for AI coding assistants (and humans) working on **Transept**, the graphical interface of Transept.

## What this project is

A Streamlit interface for Transept core (a Java tool in its own repository,
<https://github.com/jMetal/Transept-core>). Transept never reimplements the algorithm: it builds
the command line of the core's `run` command,
launches the jar as a detached process, and reads the files the tool writes. Those files and the
command-line options are the contract between both projects; they are documented in
Transept core's `docs/reference/cli.md` and `docs/reference/outputs.md`.

## Layout

| Path | Role |
| --- | --- |
| `app.py` | Navigation shell (`st.navigation`) |
| `pages/` | One script per page; only `st.session_state` survives between them |
| `transept/settings.py` | Paths of the jar, the data and the runs (`TRANSEPT_HOME`, `TRANSEPT_CORE_JAR`, `lib/`, `examples/`) |
| `transept/datasets.py` | Datasets, seed tools and topology files of a data directory |
| `transept/options.py` | The options of `run` offered by Transept; keep them in step with the CLI |
| `transept/runner.py` | Command line, detached launch, cancellation |
| `transept/runs.py` | State of a run and reading of its files |
| `transept/front.py`, `charts.py`, `alignment.py` | Non-dominated solutions, figures, alignment viewer |
| `transept/ui.py` | Page paths and the selected run |

## Rules

- The state of a run comes only from files: `metadata.json` (written last by the tool) means
  finished, `error.json` failed; `runs/jobs/<dataset>/<run-id>/` holds the PID, the log and the
  cancellation mark. Never keep run state only in memory.
- The tool refuses to write into an existing run directory: never create
  `runs/ejecuciones/<dataset>/<run-id>/` from Transept.
- When Transept core adds or removes an option value, update `transept/options.py`.
  `tests/test_options_drift.py` compares it with the help of the configured jar and fails when
  they differ (it is skipped if the jar is not available).
- Test the logic in `transept/` with pytest, and every page with `streamlit.testing.v1.AppTest`
  (`tests/test_pages.py`). Tests use the fixtures of `tests/conftest.py` (an isolated home,
  a toy data directory, runs in every state); they must not need the real jar or data.
- `make lint` and `make test` must pass before every commit. Follow `GIT_GUIDELINES.md`.
- Code, comments and documentation in English.
- Local use only for now: no authentication, no remote execution.
- `examples/GPCRdb/` holds one small dataset (`classT2_19`) copied from Dataset_Structural_GPCRs
  v1.0.0; keep it small and do not add run outputs or large data to the repository.
- Internal notes and review documents do not belong in this repository.
