# Transept

_Multiobjective, structure-guided alignment of transmembrane proteins._

Transept aligns transmembrane proteins, such as G protein-coupled receptors (GPCRs), using their
topology and AlphaFold2 structures. It refines the alignments of existing tools (or alignments it
computes itself) with multiobjective evolutionary algorithms, and offers a set of alternative
alignments that trade sequence and structural consistency. This repository is the graphical
interface: launch runs, follow them while they are active, and explore the alignments they find,
without using the command line. The engine is [Transept core](https://github.com/jMetal/Transept-core).

> **Status: prototype (0.1).** For local use. Please report problems and suggestions in the
> [issues](https://github.com/jMetal/Transept/issues).

## What it does

| Page | |
| --- | --- |
| **Home** | Checks that Java, the core jar and the data directory are available, and edits their paths |
| **New run** | Choose a dataset, the seed alignments, the objectives and the algorithm with its configuration; shows the equivalent command line |
| **Monitor** | Follows a run live (evaluations, best values), cancels it, or shows why it failed |
| **Results** | The alignments of a finished run with their extremes, knee and seed alignments; pick an alignment from the chart, the table or a list, browse it helix by helix (gaps that break a helix in red), compare it with a seed or another solution, and download it as FASTA, Clustal, Stockholm with topology or Jalview features |
| **History** | Every run with its state; open one in the monitor or the results, or move runs to the trash (restorable until it is emptied) |

## Installation

Requirements: [Conda](https://docs.conda.io/) (it installs Python 3.11 and Java 21) and the
Transept core jar, `transept-core-0.1.0-jar-with-dependencies.jar`.

```bash
git clone https://github.com/jMetal/Transept.git
cd Transept
make setup JAR=/path/to/transept-core-0.1.0-jar-with-dependencies.jar
make run      # opens Transept in the browser
```

`make setup` creates the `transept` Conda environment and copies the jar to `lib/`. To build the
jar yourself, see [Building from source](https://github.com/jMetal/Transept-core#building-from-source)
in Transept core. If you clone Transept-core next to this repository and build it there,
`make setup` (without `JAR=`) finds the jar by itself.

## Data

Transept starts with a small example in `examples/GPCRdb/`: the `classT2_19` dataset (19 taste
receptors type 2), with its predicted topology, AlphaFold2 distance matrices, six seed
alignments (ClustalW, Kalign, MAFFT, MUSCLE5, T-Coffee and TM-Aligner) and the GPCRdb reference
alignment. A run of a few hundred evaluations takes seconds.

For more datasets, use the GPCR structural benchmark
[Dataset_Structural_GPCRs](https://github.com/TM-M2StructAlign/Dataset_Structural_GPCRs)
(version v1.0.0, [DOI 10.5281/zenodo.23243974](https://doi.org/10.5281/zenodo.23243974)) and set
the data directory on the home page to its `GPCRdb` folder:

```bash
git clone https://github.com/TM-M2StructAlign/Dataset_Structural_GPCRs.git
git -C Dataset_Structural_GPCRs checkout v1.0.0
```

Your own data must follow the same layout; tutorial
[T6](https://github.com/jMetal/Transept-core/blob/main/docs/tutorials/T6-your-own-dataset.md)
of Transept core describes it.

## How it works

Transept runs the core jar as a separate process and talks to it only through files:

```text
Transept (Streamlit) ── java -jar transept-core-...jar run ... ──> runs/ejecuciones/<dataset>/<run-id>/
                                                                     config.json, progress.jsonl,
                                                                     FUN.csv, MSASol<i>.fasta,
                                                                     metadata.json or error.json
```

Runs are detached processes: closing or reloading the browser does not stop them, and reopening
Transept finds them again. Everything is kept in plain files:

| Path | Contents |
| --- | --- |
| `runs/ejecuciones/` | What the core writes for each run |
| `runs/jobs/` | What Transept keeps about each run: request, process id, log, cancellation mark |
| `runs/trash/` | Deleted runs, until the trash is emptied |
| `runs/baselines/` | Cached objective values of the seed alignments |
| `settings.json` | The paths of the jar and the data |

`TRANSEPT_HOME` moves the settings and the runs to another directory, and `TRANSEPT_CORE_JAR`
sets the jar.

## Development

```bash
make lint     # ruff check .
make test     # pytest
```

Read [AGENTS.md](AGENTS.md) and [GIT_GUIDELINES.md](GIT_GUIDELINES.md) before contributing.

## License

Transept is free software, distributed under the
[GNU General Public License v3.0](LICENSE).
