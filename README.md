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

The pages are grouped by what you want to do; the home page has a card for each one.

| Section | Page | |
| --- | --- | --- |
| | **Home** | What Transept offers; checks that Java, the core jar and the data are available, and edits the path of the jar |
| **Explore** | **Datasets** | The datasets of your repositories, and whether each one is ready to use (its checklist, proteins and seed alignments); add other data directories, and go straight to optimising a dataset |
| | **Add dataset** | Add your own proteins: give their files, check them against a checklist, and Transept computes the distances from the structures |
| | **Algorithms** | What you can optimise with: every algorithm with its objectives and parameter space, read from the core jar, and the objectives and operators; go straight to using an algorithm |
| **Optimize** | **New run** | Choose a dataset, the seed alignments, the objectives and the algorithm with its configuration; shows the equivalent command line |
| | **Monitor** | Follows a run live (evaluations, best values), cancels it, or shows why it failed |
| | **History** | Every run with its state; open one in the monitor or the results, or move runs to the trash (restorable until it is emptied) |
| **Analyze** | **Results** | The alignments of a finished run with their extremes, knee and seed alignments; pick an alignment from the chart, the table or a list, browse it helix by helix (gaps that break a helix in red), compare it with a seed or another solution, and download it as FASTA, Clustal, Stockholm with topology or Jalview features |
| | Compare | Coming soon: compare runs, seed alignments and alignments of other tools |
| **Advanced** | Automatic configuration | Coming soon |
| **Learn** | **Tutorials** | Step-by-step guides, read inside Transept |

## Installation

### What you need

| | |
| --- | --- |
| **Operating system** | macOS or Linux. On Windows, use [WSL](https://learn.microsoft.com/windows/wsl/install) (not tested yet) |
| **git and make** | macOS: `xcode-select --install`. Debian/Ubuntu: `sudo apt install git make` |
| **Conda** | [Miniforge](https://github.com/conda-forge/miniforge) is recommended; Anaconda or Miniconda also work. Conda installs Python, Java and Maven for Transept, in an environment of its own: you do not need to install them yourself |
| **Disk and network** | About 2 GB, downloaded once: the Conda environment and the libraries of Transept core |

Check that the tools are available (each command prints a version):

```bash
git --version
make --version
conda --version
```

### Steps

1. Get Transept and its engine, [Transept core](https://github.com/jMetal/Transept-core), side
   by side in the same folder:

   ```bash
   git clone https://github.com/jMetal/Transept.git
   git clone https://github.com/jMetal/Transept-core.git
   cd Transept
   ```

2. Install (about five minutes the first time):

   ```bash
   make setup
   ```

   It creates the `transept` Conda environment, builds the core jar in `../Transept-core` with
   the Maven of that environment, and copies it to `lib/`. It ends with
   `Copied ../Transept-core/target/transept-core-0.1.0-jar-with-dependencies.jar to lib/`.

3. Start Transept:

   ```bash
   make run
   ```

   The terminal shows `URL: http://localhost:8501` and the browser opens that page (open it by
   hand if it does not). Keep the terminal open while you use Transept; `Ctrl+C` stops it. Runs
   already launched keep running when Transept stops, and it finds them again on the next
   `make run`.

Transept only listens on your own machine (`localhost`): it is not reachable from the network.

To update Transept later, run `git pull` in both folders, then `make setup` (it updates the
environment) and `make core` (it rebuilds the jar) in `Transept`.

If you already have the jar (`transept-core-0.1.0-jar-with-dependencies.jar`), you do not need
Transept-core: run `make setup JAR=/path/to/the.jar` instead.

### Your first run

1. **Home** should say _Ready_, with the Java version and _1 dataset in 1 repository_ (the
   example). If it lists problems instead, see [Troubleshooting](#troubleshooting).
2. Open **New run**. The dataset is `classT2_19`, the seed alignments are `internal` (computed
   by Transept), and the algorithm is NSGA-II with its default configuration and 10 000
   evaluations. Press **Launch**.
3. **Monitor** follows the run: evaluations and the best values of both objectives. It takes between
   half a minute and two minutes, depending on the computer.
4. When it finishes, open **Results**: every dot of the chart is an alignment; pick one to see
   it helix by helix, compare it with the seed alignments and download it.

To try the seed alignments of other tools, choose them in **Seed alignments** on the **New run**
page (for example `mafft`, `muscle5` and `tmaligner`).

### Troubleshooting

| Message or problem | What to do |
| --- | --- |
| `conda: command not found` | Install Miniforge, then open a new terminal |
| `make setup` ends with _No jar found_ | Clone Transept-core next to Transept (step 1) and run `make setup` again, or pass a jar with `make setup JAR=/path/to/the.jar` |
| `make setup` fails while building the jar | Check the network connection (Maven downloads the libraries of Transept core) and run `make core` |
| Home: _Java was not found_ | Run `make setup` again, and start Transept with `make run` (it uses the Java of the environment) |
| Home: _The jar was not found at ..._ | Run `make setup JAR=...`, or set the path of the jar in the **Settings** of the home page |
| Datasets: _... does not look like a data directory_ | Add a folder with `sequences/tmregions/`, such as the `GPCRdb` folder of the benchmark |
| A dataset is _Not usable_ | **Datasets** shows what is wrong in its checklist |
| `Port 8501 is already in use` | Transept (or another Streamlit app) is already running: use that one, or stop it |
| A run fails | The **Monitor** shows why; the full output of the run is in `runs/jobs/<dataset>/<run-id>/log.txt` |

To remove Transept, delete the `Transept` folder and the environment:
`conda env remove -n transept`. Deleting the folder also deletes what you added and computed in it
(`datasets/`, `runs/` and `settings.json`), unless `TRANSEPT_HOME` keeps them elsewhere: copy
anything you want to keep first.

## Data

Transept starts with a small example in `examples/GPCRdb/`: the `classT2_19` dataset (19 taste
receptors type 2), with its predicted topology, AlphaFold2 distance matrices, six seed
alignments (ClustalW, Kalign, MAFFT, MUSCLE5, T-Coffee and TM-Aligner) and the GPCRdb reference
alignment. A run of a few hundred evaluations takes seconds. The origin and licence of these
files are described in [examples/README.md](examples/README.md).

For more datasets, use the GPCR structural benchmark
[Dataset_Structural_GPCRs](https://github.com/TM-M2StructAlign/Dataset_Structural_GPCRs)
(version v1.0.0, [DOI 10.5281/zenodo.23243974](https://doi.org/10.5281/zenodo.23243974)), and add
its `GPCRdb` folder as a repository on the **Datasets** page:

```bash
git clone https://github.com/TM-M2StructAlign/Dataset_Structural_GPCRs.git
git -C Dataset_Structural_GPCRs checkout v1.0.0
```

To align your own proteins, follow the tutorial
[Add your own proteins](docs/tutorials/add-your-own-proteins.md), also available on the
**Tutorials** page and in **Add dataset**. To use a folder of datasets
without copying it, add it on the **Datasets** page; it must follow the same layout, which tutorial
[T6](https://github.com/jMetal/Transept-core/blob/main/docs/tutorials/T6-your-own-dataset.md) of
Transept core describes.

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
| `datasets/` | The datasets added on the **Add dataset** page (the repository _My datasets_) |
| `.staging/` | Datasets being checked, before they are added |
| `settings.json` | The path of the jar and the repositories you added |

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
