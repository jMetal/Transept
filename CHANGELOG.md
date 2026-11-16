# Changelog

All notable changes to Transept are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Sections by use case: Explore, Optimize, Analyze and Learn, with a home page that leads to them.
- **Datasets**: several repositories of datasets, with a check of what each dataset has.
- **Add dataset**: your own proteins from a three-line topology file and PDB files, with a
  checklist; the distances are computed from the structures and seed alignments are optional.
- **Algorithms**: the algorithms, objectives and operators of the core jar, with their parameter
  spaces.
- **New run**: every algorithm and formulation, the operators with their settings, the
  configuration of NSGA-II, SPEA2 and the genetic algorithm, independent runs that share the
  computer automatically, and the equivalent command line.
- **Monitor**: progress of runs and series; stop them early keeping their results, or cancel them.
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
