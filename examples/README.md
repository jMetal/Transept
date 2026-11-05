# Example data

`GPCRdb/` holds one small dataset, `classT2_19` (19 taste receptors type 2), so that Transept can
be tried without downloading anything else. It is the default data directory.

| Path | Contents |
| --- | --- |
| `sequences/tmregions/classT2_19_predicted_topologies.3line` | Sequences and predicted transmembrane topology |
| `sequences/fasta/classT2_19.fasta` | Unaligned sequences |
| `distances/classT2_19/` | Cα distance matrices of the AlphaFold2 models (`<protein>_D.csv`, `<protein>_idx.csv`) |
| `alphafold_pdb/classT2_19/` | AlphaFold2 models |
| `precomputed/classT2_19/` | Seed alignments of ClustalW, Kalign, MAFFT, MUSCLE5, T-Coffee and TM-Aligner |
| `reference_alignments/classT2_19.fasta` | GPCRdb reference alignment |

## Origin and licence

The files are copied unchanged from the GPCR structural benchmark
[Dataset_Structural_GPCRs](https://github.com/TM-M2StructAlign/Dataset_Structural_GPCRs),
version v1.0.0 ([DOI 10.5281/zenodo.23243974](https://doi.org/10.5281/zenodo.23243974)), and
are distributed under the GNU General Public License v3.0, like the rest of this repository.
The AlphaFold2 models come from the [AlphaFold Protein Structure Database](https://alphafold.ebi.ac.uk/),
whose data are available under CC BY 4.0.

If you use these data, please cite:

> Zambrano-Vega, C., Cedeño-Muñoz, J., and Nebro, A. J. (2026). A Curated Dataset of Human GPCR
> Sequences, AlphaFold-Predicted Structures, Transmembrane Topologies, and Reference Alignments for
> Structural Bioinformatics (Version 1.0.0) [Dataset]. Zenodo.
> <https://doi.org/10.5281/zenodo.23243974>

For the other datasets of the benchmark, clone Dataset_Structural_GPCRs and set the data
directory of Transept to its `GPCRdb` folder.
