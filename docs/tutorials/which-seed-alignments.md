# Which seed alignments to start from

| | |
| --- | --- |
| **Level** | Basic |
| **Time** | About 10 minutes, plus a few minutes for the two runs |
| **Prerequisites** | [Overview](overview.md); the example dataset is enough |
| **You will use** | **New run** and **Results** |

A search starts from alignments, the *seeds*, and combines and improves them. They can come from two
places:

- the **internal** seeds: up to 10 alignments that Transept computes itself. Nothing else is needed,
  but they all come from one sequence aligner with different gap penalties;
- the alignments of **other tools** (MAFFT, MUSCLE, Kalign, FoldMason...), which you compute before and
  give to Transept.

Does it matter which ones you use? This tutorial shows what happened in the cases we have studied. They
are 15 datasets of one family of proteins, the G protein-coupled receptors: take them as a reference to
decide, not as a rule for your proteins.

## Try it with the example

The dataset `classT2_19` (19 bitter taste receptors) comes with the alignments of six sequence aligners
and a reference alignment, so both options can be compared.

1. Open **New run** and choose `classT2_19`. The seeds proposed are the six tools. Set **Stop after** to
   10,000 evaluations and the random seed to 1, and launch it.
2. Launch it again, with only `internal` as seed alignments. **New run** tells you that the alignments
   of other tools are recommended, and lets you go on.
3. Open both in **Results** and compare them with the reference.

This is what we got for the recommended alignment (the knee):

| | Internal seeds | Six sequence aligners |
| --- | --- | --- |
| Time (4 threads, on a laptop) | 0.7 min | 1.7 min |
| Alignments in the front | 5 | 72 |
| Agreement between them | 100 % | 99.6 % |
| SOPwTP | 70,073 | 72,609 |
| lDDT | 0.812 | 0.818 |
| Pair F1 | 0.907 | 0.916 |
| TM-pair F1 | 1.000 | 1.000 |
| Gaps inside helices | 0 | 0 |

Two things can be seen here:

- The results are close, and the helices are the same. For this dataset, either option would do.
- With the internal seeds the search found few alternatives, and they agree almost completely. **A high
  agreement does not mean that the alignment is better**: seeds that are alike give alternatives that
  are alike.

One run of each is not enough to say that a difference this small is real.

## What happened in other datasets

We ran both options on the 15 datasets with 50,000 evaluations and 10 random seeds (20 in some cases).
The other tools were six sequence aligners and, in the 11 datasets where their alignments can be used,
three structural ones (FoldMason, MUSTANG and US-align). Five of the small datasets, chosen to show
the different situations:

| Dataset | Pair F1, internal | Pair F1, other tools | TM-pair F1, internal | TM-pair F1, other tools |
| --- | --- | --- | --- | --- |
| `classB1` | 0.640 (0.624–0.655) | 0.621 (0.611–0.630) | 0.998 | 0.998 |
| `classT2_19` | 0.931 (0.926–0.942) | 0.937 (0.931–0.949) | 1.000 | 1.000 |
| `classA_003_19` | 0.784 (0.780–0.787) | 0.808 (0.802–0.814) | 0.990 | 0.990 |
| `classA_004_19` | 0.684 (0.680–0.706) | 0.715 (0.709–0.720) | 0.864 | 0.925 |
| `classC_19` | 0.288 (0.279–0.292) | 0.379 (0.377–0.386) | 0.780 | 0.972 |

Median of 10 runs of the recommended alignment; in brackets, the lowest and the highest. `classA_004_19`
has no structural alignments. In all 15, by the difference of Pair F1 of the internal seeds:

| Internal seeds | Datasets |
| --- | --- |
| Better by more than 0.01 | 1 |
| Within 0.01 | 4 |
| Worse by 0.01 to 0.05 | 4 |
| Worse by more than 0.05 | 6 |

- In some datasets there was no difference worth mentioning, and in one the internal seeds gave a
  slightly better result.
- In others the result was clearly worse, in `classC_19` also inside the helices.
- No result had gaps inside helices, with either option.

We do not know in advance in which group a new family will be, and we have not separated how much of
the difference comes from the number of tools, from their quality or from using the structures.

## What this means for your proteins

- **For a first look**, the internal seeds are the quickest way: nothing to install or prepare.
- **For a result you will use**, consider aligning your proteins with a few tools, and starting from
  them. Those in the table are options, not a list to follow; a structural aligner only makes sense if
  your proteins have models.
- **You can use both**: select `internal` together with the tools. We have not measured it.
- **If you are not sure**, run both and look at what changes: the helices (**Per helix**), the motifs or
  positions you know, the 3D superposition and, for receptors, the **GPCRdb** tab. Do not choose by the
  agreement alone, nor by the objectives alone: more SOPwTP or lDDT is not always a better alignment.

To give Transept the alignments of other tools, add them in **Add dataset**, under **Seed alignments**:
one aligned FASTA file per tool, named after it (`mafft.fasta`), with all your proteins.

## Summary

| You want | Seeds |
| --- | --- |
| To try Transept on your proteins now | `internal` |
| A result you will rely on | Consider the alignments of several tools |
| To know whether it matters for your family | A run of each, compared in **Results** |
