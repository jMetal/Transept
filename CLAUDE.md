# CLAUDE.md

Transept is the graphical interface (Streamlit, Python) of a tool for the multiobjective,
structure-guided alignment of transmembrane proteins, GPCRs first. The engine is
[Transept core](https://github.com/jMetal/Transept-core), a Java command line in its own
repository. This interface never reimplements the algorithm: it launches the core jar and reads the
files it writes, so the command line and the output files are a contract between the two projects.

Both projects are developed collaboratively and are still prototypes (0.1): pages, options and
defaults may change, but every change must keep the two repositories in step.

## Current state

The pages are grouped by use case (`transept/sections.py`):

- **Explore**: Datasets (several repositories of datasets, each checked), Add dataset (your own
  proteins from UniProt accessions, with AlphaFold models, or from your files; distances computed
  from the structures), Algorithms (read from the jar).
- **Optimize**: New run (NSGA-II with a recommended configuration of 50,000 evaluations and repaired
  seeds; in expert mode, off by default, every algorithm and formulation; several independent runs),
  Monitor, History.
- **Analyze**: Results of a run (the front, knee and medoid, agreement, the alignment helix by helix,
  support, pLDDT and conservation tracks, GPCRdb generic numbers, metrics against a reference, 3D
  superposition, downloads), Results of independent runs (the aggregate front, analysed like a
  single run, with support from the other runs), Repair alignment.
- **Learn**: the tutorials of `docs/tutorials/`, also shown inside the tool.
- **Not yet built**: Compare (runs, seeds and other tools; shown as "Coming soon").
- **Installation**: `make setup` with Conda on macOS and Linux, and a Docker image built locally
  (`make image`), not published yet.
- **Quality**: about 490 tests (pytest and `AppTest`), ruff; GitHub Actions runs them on Linux,
  also against a jar built from Transept core.
- **Data**: `examples/GPCRdb/` holds one small dataset (`classT2_19`) for a first run; the benchmark
  is Dataset_Structural_GPCRs v1.0.0 (Zenodo). See `CHANGELOG.md` (`[Unreleased]`).

## Open lines of work

Contributions are welcome in any of these; open an issue first to agree on the approach.

- The Compare page: runs, seed alignments and alignments of other tools side by side.
- Comparative studies of algorithms and configurations, in expert mode.
- A first release, a published Docker image, and an installation that works on a clean macOS or
  Linux machine (and Windows through WSL or Docker, not tested yet).
- Datasets of other transmembrane families, and better support for proteins without a GPCRdb
  numbering.
- Usability: clearer messages, faster pages on large datasets, and more tutorials.

## Getting started

```bash
# Side by side: this repository and the engine
git clone https://github.com/jMetal/Transept.git
git clone https://github.com/jMetal/Transept-core.git
cd Transept
git switch develop
make setup      # Conda environment (Python, Java, Maven) and the core jar in lib/
make lint       # ruff
make test       # pytest; must pass before any commit
make run        # opens http://localhost:8501
```

After a `git pull` in Transept-core, `make core` rebuilds the jar. The first run of the README
(New run on `classT2_19`) takes a few minutes; the example of the home page is shorter.

## How to contribute

- Start a branch from `develop` (`feat/...`, `fix/...`, `docs/...`) and open a pull request into
  `develop`. Only the maintainers merge `develop` into `main`.
- Commits follow `GIT_GUIDELINES.md` (Conventional Commits, one logical change per commit, code,
  tests and docs in separate commits, every commit passes `make lint` and `make test`).
- Keep the logic in `transept/` without Streamlit, and the pages in `pages/` thin; test both
  (`tests/test_pages.py` uses `streamlit.testing.v1.AppTest`). Tests must not need the real jar or
  data.
- A change in the command line or the outputs of Transept core needs the matching change here,
  in a pull request of its own (skill `cli-contract`).
- A new user-facing feature comes with its line in `CHANGELOG.md` and, if it changes how people
  work, a tutorial or a section in `docs/tutorials/`.

Project skills (`.claude/skills/`): `check` runs every check before a commit or a pull request;
`cli-contract` lists what to update when the command line or the outputs of the core change.

## Rules for the assistant

- Never push, open pull requests, create tags or publish anything unless the user asks, each time.
  Never commit to `main`.
- Run `make lint` and `make test` before proposing a commit, and report failures with their output.
- Never leave a Streamlit server or a test run going in the background once you are done.
- GPCRdb, UniProt and AlphaFold DB are contacted only when the user presses a button.
- Do not commit run outputs, downloaded proteins or large data, and never modify the published
  v1.0.0 files of Dataset_Structural_GPCRs.
- Code, comments, commit messages and documentation in English.

The rules and the layout of the project are in the files below; read them before changing code.

@AGENTS.md
@GIT_GUIDELINES.md
