# Changelog

All notable changes to Transept are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- NSGA-II, SPEA2 and the genetic algorithm create 100 offspring per generation by default, whatever
  the population size, and offer 1, 5, 10, 20, 50, 100, 200 or 400. The population of the search with
  an external archive goes up to 200. **Population size** changes in steps of 10, and NSGA-III no
  longer needs a multiple of 4. Needs a Transept core that does so.
- The **random choice** mutation picks one of the four mutations, not only the gap shift or the merge
  of gap runs. Needs a Transept core that does so.
- **Expert mode**, off by default and kept in the settings. Without it, **New run** searches with
  NSGA-II, SOPwTP and lDDT and the recommended configuration, whose settings are optional, and
  **Algorithms** shows only NSGA-II. With it, both offer every algorithm and formulation, as before.
- **New run** proposes the recommended configuration, chosen with a pilot on the GPCR benchmark:
  50,000 evaluations (was 10,000), **Repair the seeds** on, and as seeds the precomputed alignments of
  the sequence and structural aligners when the dataset has them (internal seeds otherwise). The
  example of the home page keeps 10,000 evaluations, as a short demonstration, and repairs its seeds.
- The internal seeds are always repaired; **Repair the seeds** applies to the precomputed ones. Needs
  a Transept core whose `run` accepts `--no-repair-seeds`.

### Removed

- The **Automatic configuration** page announced as coming soon, and the Advanced section.

### Fixed

- **Results** kept saying that GPCRdb did not answer for some receptors after a second attempt got
  them.
- **Algorithms** said that there is a single crossover; there are two.
- The 3D view said that the marked column is red; it is yellow.
- `make core` and the settings found only the jar of Transept core 0.1.0. The jar is now copied to
  `lib/transept-core.jar` whatever its version, and a jar of an earlier version saved in the
  settings from `lib/` gives way to it.
- What the interface and the tutorials say about the support of the columns: the figures are those of
  the recommended configuration, and high support is not a sign that a column is right.
- What the interface and the tutorials say about helices: the search never opens a gap inside a
  transmembrane helix, but keeps those that the seed alignments already have (**Repair the seeds**
  in **New run** moves them out first). The subtitle of the home page no longer promises whole
  helices.

### Added

- **Results of independent runs**: the detailed analysis of an alignment of the aggregate front
  (its knee at first, or the one chosen in the chart or the table), with all the tabs of a single
  run, without leaving the aggregate; **Open it in its run** shows it among the rest of its run.
  The agreement of the aggregate front, as for a run, and **Knee or medoid?** for its knee and its
  medoid (a consensus of the runs); the GPCRdb consistency of every alignment of the aggregate
  once the numbering has been fetched. An alignment of a series measures its **Support** with the
  fronts of the other runs by default (**Support from**), which on the GPCR benchmark told right
  from wrong columns better than the run alone (median AUC 0.81 against 0.72).
- **Repair alignment** (Analyze): moves the gaps that split a transmembrane helix out of any
  alignment, without search, with the `repair` command of Transept core; shows the gaps inside
  helices before and after and, with a reference, what changed. Tutorial *Gaps inside helices, and
  how to repair them*. Needs a core jar with the `repair` command (`make core`).
- Sections by use case: Explore, Optimize, Analyze and Learn, with a home page that leads to them.
- **Datasets**: several repositories of datasets, with a check of what each dataset has.
- **Add dataset**: your own proteins from their UniProt accessions (sequences and topology from
  UniProt, structure models from AlphaFold DB, fetched on request and kept) or from a three-line
  topology file and PDB files, with a checklist; the distances are computed from the structures and
  seed alignments are optional.
- **Algorithms**: the algorithms, objectives and operators of the core jar, with their parameter
  spaces.
- **New run**: every algorithm and formulation, the operators with their settings, the
  configuration of NSGA-II, SPEA2 and the genetic algorithm, independent runs that share the
  computer automatically, and the equivalent command line.
- **New run** says, when a search would start from the internal seeds alone, that the alignments of
  several tools are recommended, and how to use them. Tutorial *Which seed alignments to start
  from*, with what happened in the datasets studied.
- **Monitor**: progress of runs and series; stop them early keeping their results, or cancel them. It
  says when the best values have not improved for a number of generations (10 by default, adjustable),
  without stopping anything; the notice goes away if they improve again.
- **History**: runs and series, with a trash to restore them.
- **Results**: the front of two or three objectives with its extremes and knee, the seed alignments
  (precomputed or internal), the alignment helix by helix with the gaps that break a helix, metrics
  against a reference alignment, per-protein and per-helix views, comparison with a seed or another
  solution, the structures superposed in 3D, the aggregate of a series, and downloads in FASTA,
  Clustal, Stockholm, Jalview features, and a package for ChimeraX and PyMOL.
- Tracks in the alignment viewer, with the residues coloured by any of them: the support of every
  column by the other alignments of the run, the AlphaFold confidence (pLDDT) of every residue,
  and the conservation and consensus of every column; their means per helix.
- How much the alignments of the front agree, overall and in every helix, above the chart; the
  medoid of the front (the alignment that agrees most with the others), marked in the chart and
  compared with the knee when they differ; the alignment without its columns of low support, to
  download.
- GPCRdb generic numbers, fetched on request and kept: how many residues of the helices are in
  the column of their number, the x.50 position of every helix and the motifs DRY, CWxP, NPxxY
  and PIF.
- Tutorials inside the interface: Overview, Add your own proteins and Choose the operators.
- An example dataset that runs in a couple of minutes.
- A Docker image for Intel and ARM machines (`make image`, `make image-multiarch`).
