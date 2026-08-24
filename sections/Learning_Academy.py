import pandas as pd
import streamlit as st

import auth
from utils import inject_global_ui, render_navigation, render_page_header, render_top_nav, render_table


st.set_page_config(page_title="Learning Academy", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

render_page_header(
    "QA/QC Learning Academy",
    "Structured learning paths for civil works inspection, NDT, Barcol hardness, piping, welding, CWI, SCWI, document control, and quality leadership.",
    "Inspection Competence Centre",
)

learning_paths = [
    {
        "Path": "Civil Works Inspection",
        "Level": "Foundation",
        "Modules": "ITP review, excavation, backfill, rebar, formwork, concrete placement, curing, repair control",
        "Practical output": "Civil inspection checklist and daily quality report",
    },
    {
        "Path": "Concrete Inspection",
        "Level": "Foundation to intermediate",
        "Modules": "Mix design review, batching, slump, temperature, sampling, cubes/cylinders, curing, defects, repair method statements",
        "Practical output": "Pour readiness pack and test result tracker",
    },
    {
        "Path": "NDT Testing",
        "Level": "Intermediate",
        "Modules": "VT, PT, MT, UT, RT principles, technique sheets, calibration, limitations, report review, rejectable indications",
        "Practical output": "NDT report review checklist",
    },
    {
        "Path": "Barcol Test",
        "Level": "Specialist awareness",
        "Modules": "Composite/FRP hardness purpose, surface preparation, instrument verification, reading pattern, acceptance by specification",
        "Practical output": "Barcol hardness test record template",
    },
    {
        "Path": "Piping Inspection",
        "Level": "Intermediate",
        "Modules": "Material receiving, PMI, fit-up, weld mapping, supports, pressure testing, reinstatement, flange management",
        "Practical output": "Piping test pack readiness checklist",
    },
    {
        "Path": "Welding Inspection",
        "Level": "Intermediate to advanced",
        "Modules": "WPS/PQR, welder qualification, consumable control, preheat, interpass, visual acceptance, repair control",
        "Practical output": "Weld inspection and repair-rate dashboard inputs",
    },
    {
        "Path": "CWI Preparation",
        "Level": "Advanced",
        "Modules": "Welding processes, symbols, discontinuities, procedure qualification, inspection tools, code navigation, ethics",
        "Practical output": "Personal study plan and mock inspection report",
    },
    {
        "Path": "SCWI / Quality Leadership",
        "Level": "Senior",
        "Modules": "Quality systems, audit leadership, procedure governance, competency control, NCR strategy, management reporting",
        "Practical output": "Quality improvement roadmap",
    },
]

tab_paths, tab_matrix, tab_quiz, tab_records = st.tabs(
    ["Learning Paths", "Competency Matrix", "Knowledge Check", "Training Records"]
)

with tab_paths:
    selected_path = st.selectbox("Choose learning path", [item["Path"] for item in learning_paths])
    item = next(path for path in learning_paths if path["Path"] == selected_path)
    st.markdown(
        f"""
<div class="learning-card">
    <div class="card-eyebrow">{item["Level"]}</div>
    <h3>{item["Path"]}</h3>
    <p><strong>Modules:</strong> {item["Modules"]}</p>
    <p><strong>Practical output:</strong> {item["Practical output"]}</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("#### Suggested lesson sequence")
    sequence = pd.DataFrame(
        [
            ["1", "Read project specification, ITP, and acceptance criteria"],
            ["2", "Review common defects and inspection evidence examples"],
            ["3", "Perform a guided checklist exercise"],
            ["4", "Complete NCR / observation scenario"],
            ["5", "Supervisor review and competence sign-off"],
        ],
        columns=["Step", "Activity"],
    )
    render_table(sequence)

with tab_matrix:
    matrix = pd.DataFrame(learning_paths)
    render_table(matrix)
    st.info("Use this as a starting point for a formal competency matrix. Final authorisation should be controlled by project QA management.")

with tab_quiz:
    st.subheader("Quick Knowledge Check")
    st.caption("Answer all three questions, then submit once to receive a scored result.")
    with st.form("academy_knowledge_check", border=True):
        q1 = st.radio(
            "Before a concrete pour, which item should be confirmed first?",
            ["Paint DFT report", "Approved ITP/drawings and pour readiness", "Final dossier index"],
        )
        q2 = st.radio(
            "A root cause statement should normally describe:",
            ["The symptom only", "The verified system/process cause", "The person to blame"],
        )
        q3 = st.radio(
            "For welding inspection, the inspector should verify:",
            ["WPS, welder qualification, consumable control, and inspection acceptance", "Only final paint colour", "Only the delivery note"],
        )
        score_submitted = st.form_submit_button("Score knowledge check", type="primary", width="stretch")
    if score_submitted:
        score = int(q1.startswith("Approved")) + int(q2.startswith("The verified")) + int(q3.startswith("WPS"))
        st.metric("Score", f"{score}/3")
        if score == 3:
            st.success("Strong awareness. Proceed to practical assessment.")
        else:
            st.warning("Review the learning path and repeat the check.")

with tab_records:
    st.subheader("Training Record Builder")
    st.caption("Build a review-ready record before transferring it to the controlled competency register.")
    with st.form("academy_training_record", border=True):
        identity_col, training_col = st.columns(2)
        with identity_col:
            name = st.text_input("Trainee name")
            discipline = st.selectbox("Discipline", ["Civil", "Concrete", "NDT", "Piping", "Welding", "Coating", "E&I", "Quality"])
        with training_col:
            course = st.selectbox("Course", [item["Path"] for item in learning_paths])
            status = st.selectbox("Status", ["Planned", "In progress", "Completed", "Needs reassessment"])
        evidence = st.text_area("Evidence / assessor comments")
        preview_submitted = st.form_submit_button("Create training record preview", type="primary", width="stretch")
    if preview_submitted:
        if not name.strip():
            st.warning("Enter the trainee name before creating the record preview.")
        else:
            render_table(
                pd.DataFrame(
                    [{"Trainee": name, "Discipline": discipline, "Course": course, "Status": status, "Evidence": evidence}]
                )
            )
