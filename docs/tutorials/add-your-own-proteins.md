# Add your own proteins

| | |
| --- | --- |
| **Level** | Beginner |
| **Time** | About 10 minutes |
| **Prerequisites** | Transept installed; the [README](../../README.md) explains how |
| **You will use** | The files in `examples/GPCRdb/` of this repository, as if they were your own |

Transept aligns your own transmembrane proteins once it has their sequences, their topology and
their structures. In this tutorial you add a dataset on the **Add dataset** page, check that it is
complete, align it and look at the result. You do not need the command line.

## Step 1: prepare your files

| File | Needed? | What it is |
| --- | --- | --- |
| Sequences and topology | Required | A three-line file, described below |
| Structure models | At least one protein | One PDB file per protein, such as those of [AlphaFold DB](https://alphafold.ebi.ac.uk/) |
| Seed alignments | Optional | Aligned FASTA files from other tools. Transept computes its own seeds if you have none |
| Reference alignment | Optional | Aligned FASTA file, to evaluate alignments against it. New data usually have none |

The **three-line file** has three lines per protein: the identifier, the sequence, and one letter
per residue, where `M` marks the transmembrane residues:

```text
>fzd2_human | SP+TM
MRPRSALPRLLLPLLLLPAAGPAQFHGEKGISIPDHGFCQPISIPLCTDIAYNQTIMPNLLGHTNQEDAGLEVHQFYPLV...
SSSSSSSSSSSSSSSSSSSSSSSOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO...
```

Topology predictors such as [DeepTMHMM](https://dtu.biolib.com/DeepTMHMM) write this format.

**Name each PDB file after the identifier of its protein**: the structure of `fzd2_human` must be
`fzd2_human.pdb`. Capital letters do not matter, but a name such as `AF-Q14332-F1-model_v4.pdb`
must be changed.

For this tutorial, use these files of the Transept folder:

- `examples/GPCRdb/sequences/tmregions/classT2_19_predicted_topologies.3line`
- the folder `examples/GPCRdb/alphafold_pdb/classT2_19`

## Step 2: give the files to Transept

1. Start Transept with `make run` and open **Add dataset**, in the **Explore** section.
2. In **Name of the dataset**, write `my_receptors`.
3. In **Sequences and topology**, choose the three-line file.
4. In **Or a folder on this machine with those files**, write the full path of the
   `alphafold_pdb/classT2_19` folder. With only a few proteins, you can upload the PDB files instead.

Transept copies your files, so the originals are not touched.

## Step 3: check the files

Press **Check the files**. Nothing is added yet: Transept reads the files, computes the distances
from the PDB files and shows a checklist:

| Mark | Meaning |
| --- | --- |
| Green | In place |
| Blue | Worth knowing, but not a problem (for example, there is no reference alignment) |
| Orange | The dataset can be used, with a limitation (for example, a protein without a structure, which the lDDT ignores) |
| Red | The dataset cannot be used until you fix this |

For this example you should see 19 proteins, with structures for all of them, and the note
_Distances computed from the PDB files of 19 protein(s)_.

If a file was not used, a note says which one. The usual reason is that its name does not match any
identifier of the three-line file.

## Step 4: add the dataset

Press **Add to My datasets**. Transept opens **Datasets**, where `my_receptors` now appears in the
repository _My datasets_ with the status _Ready_.

## Step 5: align and look at the result

1. Press **Optimize this dataset**. **New run** opens with your dataset selected.
2. Keep the seed alignments `internal`, and press **Launch**. **Monitor** follows the run; it should
   take from half a minute to two minutes.
3. When it finishes, open **Results**: every dot of the chart is an alignment, and a sentence above
   it says how much they agree. The knee, a balanced one, is open below: browse it helix by helix,
   compare it with the others and download it.
4. To know which columns you can trust, read
   [Is my alignment reliable?](is-my-alignment-reliable.md).

## If something goes wrong

| Problem | What to do |
| --- | --- |
| _The topology file cannot be used_ | Check that it has exactly three lines per protein, and that each sequence and its topology have the same length |
| _No protein has distances_ | No PDB file matched a protein: rename them after the identifiers |
| _My datasets already has a dataset called ..._ | Choose another name |
| A seed alignment _cannot be used with this dataset_ | Its proteins or sequences differ from those of the three-line file; the **Seed alignments** tab of **Datasets** says how |
| A run fails saying that at least two distinct seeds are needed | Transept could only compute one distinct seed for your proteins: add a seed alignment from another tool |

## Going further

- To use a whole folder of datasets without copying it, add it as a repository on the **Datasets**
  page. It must have the layout described in
  [tutorial T6 of Transept core](https://github.com/jMetal/Transept-core/blob/main/docs/tutorials/T6-your-own-dataset.md),
  which also explains how structures are matched to sequences.
- Transept does not yet remove the datasets you add. To remove one, delete its files from the
  `datasets/` folder of Transept.
