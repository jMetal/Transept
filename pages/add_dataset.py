"""Explore > Add dataset: a dataset from UniProt and AlphaFold DB, or from the files of the user,
guided by a checklist."""

import pandas as pd
import streamlit as st

from transept import dataset_builder, settings, tutorials, ui, uniprot_import
from transept.dataset_builder import DatasetBuildError, DatasetFiles, Source
from transept.dataset_check import Status

STAGED = "add_dataset_staged"
SIGNATURE = "add_dataset_signature"
IMPORTED = "add_dataset_imported"
FROM_UNIPROT = "From UniProt and AlphaFold DB"
FROM_FILES = "From my files"
EXAMPLE = "P30301 P29972 P41181 Q92482 P55087 P55064 O14520 O43315"


def source_of(uploaded) -> Source:
    return Source(uploaded.name, data=uploaded.getvalue())


def signature(name: str, folder: str, *groups: list) -> tuple:
    """Identifies what the user gave, so that a checklist of other files is not shown."""
    return (
        name,
        folder,
        tuple(tuple((item.name, item.size) for item in group) for group in groups),
    )


def from_uniprot() -> tuple[Source | None, tuple[Source, ...], tuple]:
    """The proteins asked for to UniProt and AlphaFold DB, once the user has got them."""
    text = st.text_area(
        "UniProt accessions or entry names",
        placeholder=f"For example, eight human aquaporins: {EXAMPLE}",
        help="Separated by spaces, commas or lines, such as P29972 or AQP1_HUMAN.",
    )
    identifiers = uniprot_import.parse_identifiers(text)
    st.caption(
        "Transept asks [UniProt](https://www.uniprot.org) for the sequence and the topology of "
        "every protein, and [AlphaFold DB](https://alphafold.ebi.ac.uk) for its structure model, "
        "only when you press the button, sending only these identifiers. The answers are kept, so "
        "they are not asked for again. The transmembrane and intramembrane segments of UniProt are "
        "marked as transmembrane."
    )
    if st.button("Get them", icon=":material/download:", disabled=not identifiers):
        bar = st.progress(0.0, text="Asking UniProt and AlphaFold DB...")
        imported = uniprot_import.fetch(
            identifiers, lambda done, total: bar.progress(done / total, text=f"{done} of {total}")
        )
        bar.empty()
        st.session_state[IMPORTED] = (tuple(identifiers), imported)
    kept = st.session_state.get(IMPORTED)
    if kept is None or kept[0] != tuple(identifiers):
        if identifiers:
            st.caption("Press **Get them** to download these proteins.")
        return None, (), (tuple(identifiers),)
    imported = kept[1]
    if imported.entries:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "protein": entry.name,
                        "accession": entry.accession,
                        "description": entry.description,
                        "length": len(entry.sequence),
                        "membrane segments": entry.helices,
                        "AlphaFold model": entry.name in imported.models,
                    }
                    for entry in imported.entries
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    for problem in imported.problems:
        st.warning(problem)
    if not imported.entries:
        return None, (), (tuple(identifiers),)
    topology, models = uniprot_import.sources(imported)
    return topology, models, (tuple(identifiers), len(imported.entries))


def from_files() -> tuple[Source | None, tuple[Source, ...], tuple, str]:
    """The topology file and the structures the user uploads or points to."""
    st.subheader("Required")
    topology = st.file_uploader(
        "Sequences and topology (three-line file)",
        help="Three lines per protein: `>id`, the sequence, and one letter per residue, where M "
        "marks the transmembrane residues. DeepTMHMM writes this format.",
    )
    st.subheader("Structures")
    st.caption(
        "One PDB file per protein, named after its identifier (`<id>.pdb`). Transept computes the "
        "distances the lDDT needs from them. A protein without a structure is aligned, but the "
        "lDDT ignores it; at least one protein needs a structure."
    )
    models = st.file_uploader(
        "PDB files (and, if you have them, `<id>_D.csv` and `<id>_idx.csv`)",
        accept_multiple_files=True,
    )
    folder = st.text_input(
        "Or a folder on this machine with those files", help="Handy when there are many of them."
    ).strip()
    structures = tuple(source_of(item) for item in models)
    if folder:
        try:
            structures += dataset_builder.structure_sources_in_folder(folder)
        except DatasetBuildError as error:
            st.error(str(error))
    given = signature("", folder, models, [topology] if topology else [])
    return (source_of(topology) if topology else None), structures, given, folder


st.title("Add dataset")
st.write(
    "Add your own proteins to the repository _My datasets_: download them from UniProt and "
    "AlphaFold DB, or give your own files, which are copied, so the originals are not touched. "
    "Check them: the checklist says what is missing before anything is added."
)

tutorial = tutorials.tutorial_named(tutorials.ADD_YOUR_OWN_PROTEINS)
if tutorial is not None:
    # On this page, because going to another one would lose the files already uploaded
    with st.expander("Follow the tutorial", icon=":material/school:"):
        ui.show_tutorial(tutorial)

name = st.text_input(
    "Name of the dataset", help="Letters, digits, '.', '_' and '-'; for example my_receptors."
).strip()
origin = st.segmented_control(
    "Where are your proteins?", [FROM_UNIPROT, FROM_FILES], default=FROM_UNIPROT
)
if origin == FROM_FILES:
    topology_source, structures, given, _ = from_files()
else:
    topology_source, structures, given = from_uniprot()

st.subheader("Optional")
seeds = st.file_uploader(
    "Seed alignments (aligned FASTA)",
    accept_multiple_files=True,
    help="Named after the tool (for example `mafft.fasta`), with all the proteins. Transept can "
    "compute its own internal seeds, so you do not need them to start.",
)
reference = st.file_uploader(
    "Reference alignment (aligned FASTA)",
    help="Needed to evaluate alignments against a reference; new data usually have none.",
)

current_signature = (
    name,
    origin,
    given,
    signature("", "", seeds, [reference] if reference else []),
)
if st.session_state.get(SIGNATURE) != current_signature:
    st.session_state.pop(STAGED, None)

ready_to_check = bool(name and topology_source)
if st.button("Check the files", disabled=not ready_to_check):
    try:
        files = DatasetFiles(
            name,
            topology_source,
            structures,
            tuple(source_of(item) for item in seeds),
            source_of(reference) if reference else None,
        )
        with st.spinner("Reading the files and computing the distances..."):
            st.session_state[STAGED] = dataset_builder.stage(
                files, settings.staging_root(), settings.datasets_root()
            )
        st.session_state[SIGNATURE] = current_signature
    except DatasetBuildError as error:
        st.session_state.pop(STAGED, None)
        st.error(str(error))
if not ready_to_check:
    st.caption(
        "Give a name and the proteins (downloaded, or the sequences with their topology) to "
        "check them."
    )

staged = st.session_state.get(STAGED)
if staged is not None:
    st.subheader(f"Checklist of {staged.name}")
    ui.render_checks(staged.report)
    for note in staged.notes:
        st.info(note)
    usable = staged.report.status != Status.NOT_USABLE
    if not usable:
        st.error("This dataset cannot be used yet: fix what is marked in red and check it again.")
    if st.button("Add to My datasets", type="primary", disabled=not usable):
        try:
            dataset_builder.publish(staged, settings.datasets_root())
        except DatasetBuildError as error:
            st.error(str(error))
        else:
            st.session_state.pop(STAGED, None)
            st.session_state[ui.DATASET_SELECTED] = (str(settings.datasets_root()), staged.name)
            st.switch_page(ui.DATASETS)
