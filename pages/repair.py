"""Analyze > Repair alignment: the gaps inside helices of an alignment of another tool moved out."""

import tempfile
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

from transept import dataset_check, datasets, reference_scores, repair, settings, ui

RESULT = "repair_result"
FROM_DATASET = "A precomputed alignment of the dataset"
FROM_FILE = "My alignment (FASTA)"

st.title("Repair alignment")
st.markdown(
    "Most aligners place gaps inside transmembrane helices. The repair moves every gap run that "
    "splits a helix, whole, to the nearest position outside the helices; the residues keep their "
    "order and the alignment keeps its length. It is the same repair that **New run** applies to "
    "the seeds, here on its own, without any search. In the GPCR benchmark it removes every gap "
    "inside a helix and changes the accuracy of most aligners by less than 0.005 of Pair F1."
)

current = settings.load_settings()
if settings.problems(current):
    st.warning("Transept is not ready yet: check the settings.")
    st.page_link(ui.HOME, label="Go to the settings", icon=":material/home:")
    st.stop()
jar = str(current.jar)
if not repair.supported(jar):
    st.warning(
        "This version of Transept core has no `repair` command. Update it: `git pull` in "
        "Transept-core, then `make core` in Transept."
    )
    st.stop()

entries = dataset_check.catalogue(settings.all_repositories(current))
usable = [entry for entry in entries if entry.report.status != dataset_check.Status.NOT_USABLE]
if not usable:
    st.warning("There are no usable datasets yet: the topology of the proteins comes from one.")
    st.page_link(ui.DATASETS, label="Go to the datasets", icon=":material/dataset:")
    st.stop()
repeated = Counter(entry.name for entry in usable)
by_label = {
    (f"{entry.name} ({entry.repository.name})" if repeated[entry.name] > 1 else entry.name): entry
    for entry in usable
}
chosen = by_label[
    st.selectbox(
        "Dataset",
        list(by_label),
        help="The alignment must have the proteins of this dataset; their topology says where "
        "the helices are.",
    )
]
data_root, dataset = str(chosen.repository.path), chosen.name
topology = datasets.topology_file(data_root, dataset)
proteins = datasets.read_topology(topology)

source = st.segmented_control(
    "Alignment", [FROM_DATASET, FROM_FILE], default=FROM_DATASET, key="repair_source"
)
alignment_file: Path | None = None
uploaded = None
if source == FROM_DATASET:
    tools = [
        tool
        for tool in datasets.list_seed_tools(data_root, dataset)
        if datasets.seed_problem(datasets.seed_file(data_root, dataset, tool), proteins) is None
    ]
    if not tools:
        st.info(f"{dataset} has no precomputed alignments of its proteins: upload one instead.")
    else:
        tool = st.selectbox("Tool", tools)
        alignment_file = datasets.seed_file(data_root, dataset, tool)
elif source == FROM_FILE:
    uploaded = st.file_uploader(
        "Alignment (FASTA)",
        type=["fasta", "fa", "fas", "afa", "aln", "txt"],
        help="An aligned FASTA file of the proteins of the dataset, with the same residues.",
    )

signature = (data_root, dataset, str(alignment_file), uploaded.file_id if uploaded else None)
can_repair = alignment_file is not None or uploaded is not None
if st.button("Repair", icon=":material/healing:", type="primary", disabled=not can_repair):
    with tempfile.TemporaryDirectory() as scratch, st.spinner("Repairing..."):
        scratch = Path(scratch)
        if uploaded is not None:
            name = Path(uploaded.name).name or "alignment.fasta"
            alignment_file = scratch / "input" / name
            alignment_file.parent.mkdir()
            alignment_file.write_bytes(uploaded.getvalue())
        try:
            repaired = repair.repair(jar, topology, alignment_file, scratch / "repaired")
            breaks = repair.helix_breaks(repaired, proteins)
            comparison = repair.reference_comparison(jar, data_root, dataset, repaired, scratch)
        except (repair.RepairError, ValueError) as error:
            st.session_state[RESULT] = (signature, str(error))
        else:
            st.session_state[RESULT] = (
                signature,
                {
                    "name": repaired.repaired.name,
                    "moved": repaired.moved_runs,
                    "breaks": breaks,
                    "comparison": comparison,
                    "data": repaired.repaired.read_bytes(),
                },
            )

kept = st.session_state.get(RESULT)
if kept is None or kept[0] != signature:
    st.stop()
result = kept[1]
if isinstance(result, str):
    st.error(f"It could not be repaired: {result}")
    st.stop()

breaks: pd.DataFrame = result["breaks"]
columns = st.columns(3)
columns[0].metric("Gap runs moved", result["moved"])
columns[1].metric("Gaps inside helices before", int(breaks[repair.BEFORE].sum()))
columns[2].metric("After", int(breaks[repair.AFTER].sum()))
if result["moved"] == 0:
    st.success("This alignment has no gap inside a helix: there was nothing to repair.")
else:
    with st.expander(f"{len(breaks)} proteins had gaps inside helices"):
        st.dataframe(
            breaks.rename(columns={repair.BEFORE: "Before", repair.AFTER: "After"}),
            hide_index=True,
            width="stretch",
        )

comparison = result["comparison"]
if comparison is not None:
    st.subheader("Against the reference")
    shown = comparison.T
    shown["Change"] = shown[repair.AFTER] - shown[repair.BEFORE]
    st.dataframe(
        shown.rename(columns={repair.BEFORE: "Before", repair.AFTER: "After"}).style.format(
            "{:.4f}"
        ),
        width="stretch",
    )
    st.caption(
        f"{reference_scores.TM_GAP_RATE} counts transmembrane residues facing a gap in another "
        "protein, not gaps inside helices: it can go up after the repair, when a repaired helix "
        "ends up facing the gaps of other rows."
    )
elif reference_scores.has_reference(data_root, dataset):
    st.caption("The alignments could not be compared with the reference of the dataset.")

st.download_button(
    "Download the repaired alignment",
    result["data"],
    file_name=f"repaired_{result['name']}",
    mime="text/plain",
    icon=":material/download:",
)
