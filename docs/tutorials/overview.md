# Overview

Transept aligns transmembrane proteins, such as G protein-coupled receptors (GPCRs), taking into
account their topology and their 3D structures. This page explains when it is useful, what it gives
you that other aligners do not, everything you can do with it, and the usual ways of working with
it. You do not need the command line.

## The problem

A multiple sequence alignment places equivalent residues of several proteins in the same column. It
is the starting point of many analyses: finding conserved positions, transferring annotations,
building phylogenies or designing mutants.

Usual aligners rely mostly on the sequence. In transmembrane proteins this has limits: sequences can
be very divergent while their structures stay similar, and an aligner can open gaps inside a
transmembrane helix, which is rarely meaningful in biological terms. They also give you a single
alignment, with no indication of which parts of it you can trust.

## What Transept does

Transept does not start from scratch: it **refines** alignments, those of tools such as MAFFT or
T-Coffee, or others it computes itself. It searches for better ones with evolutionary algorithms,
guided by:

| Criterion | What it means |
| --- | --- |
| **Topology** | Its operators never open a gap inside a transmembrane helix |
| **Sequence** (SOPwTP) | A sum of pairs that takes the topology into account |
| **Structure** (lDDT) | Whether aligned residues keep similar distances in the 3D structures, for example those of AlphaFold |

Sequence and structure can pull in different directions, so the search ends with **a set of
alternative alignments** that trade one for the other.

## What you get that other aligners do not give you

| | What it means for you |
| --- | --- |
| **Helices kept whole** | The search never opens a gap inside a transmembrane helix. Seed alignments often have such gaps, and Results shows them in red |
| **Structure taken into account** | The AlphaFold2 (or experimental) structures guide the search, and you can see the structures superposed according to the alignment |
| **Better than its starting point** | The search starts from the alignments of other tools and keeps improving them; Results draws those seed alignments beside the result, so you see what was gained |
| **A recommended alignment** | You do not have to choose among the alignments found: the **knee**, a balanced point of the trade-off, is a good default |
| **A reliability map** | For every column, how robust it is (**support**), how reliable the structures are there (AlphaFold **pLDDT**) and how conserved it is. Columns with low support were almost never right on the GPCR benchmark |
| **An independent check for GPCRs** | The alignment checked against the GPCRdb generic numbers of the receptors: the x.50 position of every helix and the motifs DRY, CWxP, NPxxY and PIF |
| **Ready for the next step** | Downloads for Jalview (with the helices marked), ChimeraX and PyMOL (structures superposed), and a FASTA without the unreliable columns, for a tree |
| **No programming, reproducible** | Everything from the browser; every run records its options, so the same seed repeats it exactly; New run shows the equivalent command line, to run it elsewhere |
| **Your data stay with you** | Transept runs on your computer: nothing is sent anywhere, there are no queues and no size limits |

### Why a set of alignments and not one?

A tool such as ClustalW or MAFFT gives you one alignment, and no way of telling which parts of it
to trust. You do not have to choose among the alignments of Transept either: **Results** recommends
one, the knee. The set is what lets Transept tell you more:

- **How much the choice matters.** Results says how much the alignments of the set agree. On the
  GPCR benchmark they usually share 95–99 % of their residue pairs and align the helices almost
  identically: they are one answer in the helices, with variants in the loops. When they disagree
  more, as with long extracellular domains, Results says so and compares the knee with the
  **medoid**, the alignment that agrees most with all the others.
- **Which columns to trust.** The **Support** track gives, for every column, how many of the other
  alignments keep its residues together. On the GPCR benchmark, columns with support below 0.5
  were almost never right according to the reference alignment, while well-supported ones mostly
  were. You can download the alignment without its unreliable columns, for a tree for instance.

[Is my alignment reliable?](is-my-alignment-reliable.md) shows how to read these measures.

## Who it is for

- **Biologists** who want to align a family of transmembrane proteins and explore the result, helix
  by helix, without programming.
- **Bioinformaticians** who need reproducible alignments, want to compare them with those of other
  tools, or want to export them to other programs.
- **Researchers in alignment methods**, who can choose objectives, algorithms, operators and their
  parameters, repeat runs and evaluate them against a reference.

It is less suitable if you have no structures for most of your proteins, because the structural
criterion would then have little to work with, or if your proteins are not transmembrane.

## What you need

| | |
| --- | --- |
| **Sequences and topology** | Which residues of each protein are transmembrane, in a three-line file |
| **Structures** | One PDB file per protein, for example the AlphaFold2 model |
| **Seed alignments** | Optional: Transept computes its own |
| **Reference alignment** | Optional: only needed to evaluate the results against it |

Transept includes a small example, 19 bitter taste receptors, so you can try it right away.

## The sections of Transept

The home page leads to every section and shows the latest result, the runs in progress and what
Transept has to offer.

| Section | Page | What you do there |
| --- | --- | --- |
| **Explore** | **Datasets** | See the datasets of your data directories and whether they are ready; add directories, such as the GPCR structural benchmark |
| | **Add dataset** | Add your own proteins, guided by a checklist |
| | **Algorithms** | See the algorithms, objectives and operators, and the parameters of each configurable algorithm |
| **Optimize** | **New run** | Choose a dataset, seed alignments, objectives, an algorithm and its settings, and launch the search, once or several times |
| | **Monitor** | Follow runs live; stop one early keeping what it found, or cancel it |
| | **History** | Every run and series of runs; move them to the trash and restore them |
| **Analyze** | **Results** | Explore, check and download the alignments of a run (see below) |
| **Learn** | **Tutorials** | These guides |

## What you can do in Results

At the top, the **front**: every alignment found, plotted by its two objectives (or in 3D with
three), with the knee, the best alignment of each objective and, if you want, the seed alignments.
Above the chart, a sentence says how much the alignments agree. Click a point, or a row of the
table, to open its alignment; a slider finds the compromise that weighs sequence and structure as
you prefer.

Below, the chosen alignment, in tabs:

| Tab | What it shows |
| --- | --- |
| **Alignment** | The alignment, helix by helix, with the gaps that break a helix in red and tracks of TM consensus, support, pLDDT, conservation and consensus residue. Colour the residues by topology, support, AlphaFold confidence or conservation |
| **Per protein** | For every protein: its length, its gaps and runs of gaps, those inside its helices, its mean identity with the others and the state of its structure |
| **Per helix** | Whether every helix is intact, broken or displaced in each protein, with the mean support, pLDDT and conservation of the helix |
| **GPCRdb** | For receptors, how many residues of the helices are in the column of their generic number, the x.50 position of every helix and the conserved motifs. GPCRdb is only asked when you press the button |
| **Compare** | What changes between this alignment and a seed alignment or another alignment of the run, column by column |
| **3D** | The structures superposed according to the alignment, with the residues of a column marked, to see whether they really sit together |

And downloads: FASTA, Clustal, Stockholm with the topology, Jalview features, the FASTA without the
columns of low support, the structures superposed for ChimeraX and PyMOL, and a zip with the
highlighted alignments (extremes, knee, medoid, compromise).

With a reference alignment, every alignment also shows how close it is to it (see Workflow 4).

## Workflow 1: your first alignment

About five minutes, with the included example.

1. On the home page, press **Run the example**. **Monitor** follows the run, which takes one or
   two minutes.
2. Press **Open the results of this run**. Every dot of the chart is an alignment, and the knee is already
   open below.
3. Browse its alignment helix by helix: press **TM1**, **TM2**… Gaps that break a helix appear in
   red. The seed alignments in the chart show where the search started.
4. Look at the **Support** track: dark columns are the same in every alignment found; light ones
   depend on the trade-off.
5. Download it, as FASTA, Clustal or Stockholm. To see it in 3D outside Transept, download
   **Structures for ChimeraX and PyMOL**: the structures come superposed according to the
   alignment, with a script that opens them with the helices coloured.

**New run** gives you every option: the dataset, the seed alignments, what to optimise, the
algorithm and its settings.

## Workflow 2: your own proteins

1. In **Add dataset**, give a name, your sequences with their topology, and your PDB files.
2. Press **Check the files**: a checklist says what is ready and what is missing. Transept computes
   the distances from the structures.
3. Press **Add to My datasets**, and then **Optimize this dataset**.
4. Continue as in the first workflow. If you have no seed alignments, Transept computes its own.

The tutorial [Add your own proteins](add-your-own-proteins.md) explains each step.

## Workflow 3: more confidence with independent runs

The search is stochastic, so two runs do not give exactly the same alignments. Repeating it shows
how stable the results are, and together the runs can find better alignments than one.

1. In **New run**, set **Independent runs**, for example to 10. Transept decides how they share the
   computer.
2. **Monitor** draws the runs in progress in blue and the finished ones in grey.
3. **Results** shows the front of each run in grey and their **aggregate** in blue: the best
   alignments of all the runs together, with their knee. Select an alignment to open it in its run.

## Workflow 4: evaluate against a reference

If your dataset has a reference alignment, such as those of GPCRdb, **Results** shows how close each
alignment is to it:

| Metric | What it tells you |
| --- | --- |
| **Pair F1** | How well the aligned pairs agree with the reference, in the whole protein |
| **TM-pair F1** | The same, only in the transmembrane regions |
| **TM-gap rate** | How often a transmembrane residue faces a gap; lower is better |
| **Coverage** | How many pairs are aligned, relative to the reference |

The seed alignments appear beside them, so you can see what the search has gained. The search never
sees the reference: it is only used to evaluate.

To try it on more proteins, add the
[GPCR structural benchmark](https://doi.org/10.5281/zenodo.23243974), which has references for 16
datasets, as a repository on the **Datasets** page.

## Workflow 5: explore the method

For those who study the search itself:

- **What to optimise.** Three formulations: SOPwTP and lDDT (the default), lDDT alone, or both
  with coverage as a third objective, which favours alignments with more aligned pairs.
- **How to search.** NSGA-II (the default), SPEA2, a genetic algorithm, their asynchronous
  versions and others, with two random searches as a baseline. **Algorithms** lists them with
  their parameters, and **New run** lets you set them, or paste a whole configuration.
- **With what operators.** Crossovers and mutations designed so that none of them breaks a helix;
  [Choose the operators](operators.md) explains them and what we have seen them do.
- **From where.** The seed alignments of any of the tools in the dataset, those Transept computes
  itself, or both.
- **For how long.** A number of evaluations or a time limit; a run can be stopped early, keeping
  what it found.

**New run** shows the equivalent command line, to repeat a run on another computer.

## Good to know

- **Check more than one number.** A higher lDDT is not always a better alignment: the lDDT is a mean
  over the aligned residues, so it does not take into account how many residues are aligned. Look
  also at the coverage and at the gaps, especially in proteins with long regions outside the
  membrane.
- **Support measures agreement, not correctness.** A mistake shared by every alignment of the run is
  still well supported; low support, on the other hand, is a reliable warning.
- **Your work is kept.** Runs go on if you close the browser or Transept, and datasets and results
  stay until you delete them. The same seed and options reproduce a run exactly, except when it stops
  by time or uses an asynchronous algorithm with several threads.
- **Transept runs on your computer.** Your data stay there, and it cannot be reached from the network.
  The only exception is the GPCRdb numbering, which is asked for only when you press its button,
  sending only the names of the receptors.

## The tutorials

| Tutorial | What it covers |
| --- | --- |
| [Add your own proteins](add-your-own-proteins.md) | The files you need, and how to add and align them |
| [Is my alignment reliable?](is-my-alignment-reliable.md) | Support, pLDDT, conservation, the GPCRdb check, and how to read them together |
| [Choose the operators](operators.md) | The crossovers and mutations, and when each one helps |
