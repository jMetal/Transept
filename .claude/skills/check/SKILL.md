---
name: check
description: Run every check of Transept (ruff and the tests) before a commit or a pull request, and report what fails. Use before committing, before opening a pull request, or when asked whether the project is healthy.
---

# Check Transept

Run the checks that a commit and a pull request must pass. Do not commit, push or change code
here: only run and report.

1. Make sure you are in the root of Transept (`app.py` present) and note the branch
   (`git branch --show-current`). If it is `main`, say so: changes go on a branch from `develop`.
2. Lint:

   ```bash
   make lint
   ```

3. Tests:

   ```bash
   make test
   ```

   `tests/test_options_drift.py` compares `transept/options.py` with the help of the core jar and
   is skipped when there is no jar in `lib/`. If it was skipped, say so, and run `make core`
   (needs a clone of Transept-core next to this one) and `make test` again when the change touches
   options.
4. Report:
   - "All checks pass", with the number of tests, if everything passed;
   - otherwise, for every failure: the test or rule, the file and line, and the message. Quote the
     relevant output; do not paraphrase it.
5. Never call the change ready while a check fails. Do not leave a Streamlit server or a test run
   going in the background.
