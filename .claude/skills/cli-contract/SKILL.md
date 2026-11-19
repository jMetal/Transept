---
name: cli-contract
description: Keep Transept and Transept core in step when the command line, an option value, an output file or a parameter space of the core changes. Use when updating the interface after a change in Transept core, or when a feature here needs a new option or output from the core.
---

# Follow a change of the contract with Transept core

Transept drives the core only through its commands, its output files and the parameter spaces and
default configurations inside the jar (`docs/reference/cli.md` and `docs/reference/outputs.md` of
Transept core describe them). The core is the source of truth.

1. Read what changed in the core: its `CHANGELOG.md` (`[Unreleased]`), `docs/reference/cli.md` and
   `docs/reference/outputs.md`, or `git log` in the clone next to this one (`../Transept-core`).
2. Rebuild the jar: `make core`.
3. Update the interface:
   - options and their values: `transept/options.py`, and the pages that offer them
     (`pages/new_run.py`);
   - command lines and launching: `transept/runner.py`, `series.py`;
   - readers of the outputs: `transept/runs.py`, `reference_scores.py`, `baselines.py`,
     `internal_seeds.py`, `repair.py`, `algorithms.py`, `spaces.py`;
   - fixtures: `tests/conftest.py`, so that the toy runs look like real ones.
4. Older runs must still open: keep reading the previous layout of an output when it changes.
5. Run `make lint` and `make test` (the `check` skill). `tests/test_options_drift.py` must run, not
   be skipped, and pass.
6. Add the user-facing change to `CHANGELOG.md`, and to the tutorials of `docs/tutorials/` if it
   changes how people work.

Each repository gets its own commits and its own pull request into `develop`; link the two pull
requests to each other. Do not push or open them unless the user asks.
