# Overview

Transept aligns transmembrane proteins, such as G protein-coupled receptors (GPCRs), taking into
account their topology and their 3D structures. This page explains when it is useful, what you can
do with it, and the usual ways of working with it. You do not need the command line.

## The problem

A multiple sequence alignment places equivalent residues of several proteins in the same column. It
is the starting point of many analyses: finding conserved positions, transferring annotations,
building phylogenies or designing mutants.

Usual aligners rely mostly on the sequence. In transmembrane proteins this has limits: sequences can
be very divergent while their structures stay similar, and an aligner can open gaps inside a
transmembrane helix, which is rarely meaningful in biological terms.

## What Transept does

Transept does not start from scratch: it **refines** alignments, those of tools such as MAFFT or
T-Coffee, or others it computes itself. It searches for better ones with evolutionary algorithms,
guided by:

| Criterion | What it means |
| --- | --- |
| **Topology** | Its operators never open a gap inside a transmembrane helix |
| **Sequence** (SOPwTP) | A sum of pairs that takes the topology into account |
| **Structure** (lDDT) | Whether aligned residues keep similar distances in the 3D structures, for example those of AlphaFold |

Sequence and structure can pull in different directions, so Transept does not give you a single
answer: it gives you **a set of alternative alignments** that trade one for the other, and you
choose among them.

## Who it is for

- **Biologists** who want to align a family of transmembrane proteins and explore the result, helix
  by helix, without programming.
- **Bioinformaticians** who need reproducible alignments, want to compare them with those of other
  tools, or want to export them to other programs.
- **Researchers in alignment methods**, who can choose objectives, algorithms and their parameters,
  repeat runs and evaluate them against a reference.

It is less suitable if you have no structures for most of your proteins, because the structural
criterion would then have little to work with, or if your proteins are not transmembrane.

## What you need

| | |
| --- | --- |
| **Sequences and topology** | Which residues of each protein are transmembrane |
| **Structures** | One PDB file per protein |
| **Seed alignments** | Optional: Transept computes its own |
| **Reference alignment** | Optional: only needed to evaluate the results against it |

Transept includes a small example, 19 taste receptors, so you can try it right away.

## The sections of Transept

| Section | What you do there |
| --- | --- |
| **Explore** | See the datasets and whether they are ready; add your own proteins; see the algorithms |
| **Optimize** | Launch runs, follow them, and find earlier ones |
| **Analyze** | Explore, evaluate and download the alignments |
| **Learn** | These tutorials |

## Workflow 1: your first alignment

About five minutes, with the included example.

1. Open **New run**. The example dataset and the default options are already selected.
2. Press **Launch**. **Monitor** follows the run, which takes one or two minutes.
3. Press **Open the results**. Every dot of the chart is an alignment.
4. Click a dot and browse its alignment helix by helix. Gaps that break a helix appear in red.
5. Download the one you prefer, as FASTA, Clustal or Stockholm.

## Workflow 2: your own proteins

1. In **Add dataset**, give a name, your sequences with their topology, and your PDB files.
2. Press **Check the files**: a checklist says what is ready and what is missing. Transept computes
   the distances from the structures.
3. Press **Add to My datasets**, and then **Optimize this dataset**.
4. Continue as in the first workflow.

The tutorial [Add your own proteins](add-your-own-proteins.md) explains each step.

## Workflow 3: more confidence with independent runs

The search is stochastic, so two runs do not give exactly the same alignments. Repeating it shows
how stable the results are, and together the runs can find better alignments than one.

1. In **New run**, set **Independent runs**, for example to 10. Transept decides how they share the
   computer.
2. **Monitor** draws the runs in progress in blue and the finished ones in grey.
3. **Results** shows the front of each run in grey and their **aggregate** in blue: the best
   alignments of all the runs together. Select one to open it in its run.

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

## Good to know

- **Check more than one number.** A higher lDDT is not always a better alignment: the lDDT is a mean
  over the aligned residues, so it does not take into account how many residues are aligned. Look
  also at the coverage and at the gaps, especially in proteins with long regions outside the
  membrane.
- **Your work is kept.** Runs go on if you close the browser or Transept, and datasets and results
  stay until you delete them. The same seed and options reproduce a run exactly, except when it stops
  by time or uses an asynchronous algorithm with several threads.
- **Transept runs on your computer.** Your data stay there, and it cannot be reached from the network.
