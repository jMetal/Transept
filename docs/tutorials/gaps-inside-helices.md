# Gaps inside helices, and how to repair them

| | |
| --- | --- |
| **Level** | Basic |
| **Time** | About 10 minutes |
| **Prerequisites** | None: the example dataset is enough |
| **You will use** | **Repair alignment** (Analyze) and **Repair the seeds** in **New run** |

A transmembrane helix crosses the membrane in one piece. When an alignment puts a gap *inside* a
helix of a protein, it says that a stretch of that helix has no counterpart in the other proteins,
which the structures rarely support. Most aligners place such gaps, because they do not know where
the helices are: in the GPCR benchmark, MAFFT leaves a median of 51 per dataset, MUSCLE5 79, and even
TM-Aligner, which uses the topology, 45.

Transept never opens a gap inside a helix, and it can remove those of other alignments: the
**repair**. This tutorial explains what it does, and how to use it on its own or before a search.

## What counts as a gap inside a helix

In every protein, a gap run *splits a helix* when it lies between two consecutive residues of the
same helix (`M` in the topology). A gap right before the first residue of a helix, or right after
its last one, does not split it. Only the protein's own row matters: gaps of the other proteins in
the same columns are fine.

**Results** draws the gaps inside helices in red, and its **Per helix** tab tells for every helix
whether it is intact or broken.

## What the repair does

For each protein, the repair takes every gap run that splits a helix and moves it, whole, to the
nearest position outside the helices, counting residues (on a tie, towards the start of the
protein). Nothing else changes:

- the residues of every protein keep their order;
- the alignment keeps its length: a run of 2 gaps moved across 1 residue shifts that residue 2
  columns;
- proteins without gaps inside helices are left as they were.

A real case, from the MAFFT alignment of the frizzled receptors (`classF`). MAFFT puts two gaps
right after the first residue of a helix of FZD4; the nearest end of the helix is one residue back:

```text
                 before                    after
residues    QEGLKNT--GCAIIF           QEGLKN--TGCAIIF
topology    OOOOOOM  MMMMMM           OOOOOO  MMMMMMM
```

The `T` that started the helix moves two columns to the right, next to the rest of it. The repair
is a local move, not a realignment: it does not try to put the residues in better columns, only to
keep each helix in one piece.

## Repair an alignment you already have

1. Open **Repair alignment**, in **Analyze**.
2. Choose the **dataset** of the proteins: its topology says where the helices are.
3. Choose the alignment: one of the dataset's precomputed alignments, or **My alignment (FASTA)** to
   upload one made with any tool. It must have the proteins of the dataset, with the same residues.
4. Press **Repair**. Transept shows how many gap runs it moved, the gaps inside helices before and
   after (always 0 after), and which proteins had them.
5. If the dataset has a reference alignment, it also shows **Pair F1**, **TM-pair F1**, **TM-gap
   rate** and coverage before and after, so you see what the repair changed.
6. **Download the repaired alignment**.

The **TM-gap rate** may go up after the repair. It does not count gaps inside helices: it counts the
transmembrane residues of a protein that face a gap of *another* protein, and a repaired helix can
end up facing the gaps of other rows. The two measure different things.

## Repair the seeds of a search

**New run** repairs the seed alignments before the search by default (**Repair the seeds**). Since the
operators of Transept never open a gap inside a helix either, no alignment of the result has one.
Turn it off only to reproduce a run made without it.

## How much does it change an alignment?

Very little. The 11 aligners of the GPCR benchmark, repaired and compared with the GPCRdb reference
alignments (median change of Pair F1 over the datasets):

| Aligner | Change of Pair F1 |
| --- | --- |
| ClustalW, MAFFT, Kalign, FoldMason | +0.001 to +0.004 |
| MUSCLE5, T-Coffee, TM-Aligner, US-align, MUSTANG | −0.005 to −0.001 |
| mTM-align | −0.022 |

For 10 of the 11 the change stays below 0.005: the repair removes every gap inside a helix at almost
no cost in accuracy. It does not, however, make an alignment better; that is what the search does.
A Transept alignment improves on its seeds because of the search, not because of the repair.

## Summary

| To | Use |
| --- | --- |
| See the gaps inside helices of an alignment | **Results** (red gaps, **Per helix** tab) |
| Remove them from an alignment of another tool | **Repair alignment** |
| Search without them | **New run** with **Repair the seeds** (the default) |
| Do it from the command line | `transept-core repair` ([tutorial T8 of Transept core](https://github.com/jMetal/Transept-core/blob/develop/docs/tutorials/T8-repairing-helix-gaps.md)) |
