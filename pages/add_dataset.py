"""Explore > Add dataset: a dataset from the files of the user, guided by a checklist."""

import streamlit as st

from transept import dataset_builder, settings, ui
from transept.dataset_builder import DatasetBuildError, DatasetFiles, Source
from transept.dataset_check import Status

STAGED = "add_dataset_staged"
SIGNATURE = "add_dataset_signature"


def source_of(uploaded) -> Source:
    return Source(uploaded.name, data=uploaded.getvalue())


def signature(name: str, folder: str, *groups: list) -> tuple:
    """Identifies what the user gave, so that a checklist of other files is not shown."""
    return (
        name,
        folder,
        tuple(tuple((item.name, item.size) for item in group) for group in groups),
    )


st.title("Add dataset")
st.write(
    "Add your own proteins to the repository _My datasets_. Your files are copied, so the "
    "originals are not touched. Give what you have and check it: the checklist says what is "
    "missing before anything is added."
)

name = st.text_input(
    "Name of the dataset", help="Letters, digits, '.', '_' and '-'; for example my_receptors."
).strip()

st.subheader("Required")
topology = st.file_uploader(
    "Sequences and topology (three-line file)",
    help="Three lines per protein: `>id`, the sequence, and one letter per residue, where M marks "
    "the transmembrane residues. DeepTMHMM writes this format.",
)

st.subheader("Structures")
st.caption(
    "One PDB file per protein, named after its identifier (`<id>.pdb`). Transept computes the "
    "distances the lDDT needs from them. A protein without a structure is aligned, but the lDDT "
    "ignores it; at least one protein needs a structure."
)
models = st.file_uploader(
    "PDB files (and, if you have them, `<id>_D.csv` and `<id>_idx.csv`)",
    accept_multiple_files=True,
)
folder = st.text_input(
    "Or a folder on this machine with those files", help="Handy when there are many of them."
).strip()

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

current_signature = signature(
    name, folder, models, seeds, [topology] if topology else [], [reference] if reference else []
)
if st.session_state.get(SIGNATURE) != current_signature:
    st.session_state.pop(STAGED, None)

if st.button("Check the files", disabled=not (name and topology)):
    try:
        structures = tuple(source_of(item) for item in models)
        if folder:
            structures += dataset_builder.structure_sources_in_folder(folder)
        files = DatasetFiles(
            name,
            source_of(topology),
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
if not (name and topology):
    st.caption("Give a name and the sequences with their topology to check the files.")

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
