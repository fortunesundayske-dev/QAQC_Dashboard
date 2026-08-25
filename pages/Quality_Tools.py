import math

import pandas as pd
import streamlit as st

import auth
from utils import inject_global_ui, render_navigation, render_page_header, render_top_nav, render_table


st.set_page_config(page_title="Quality Tools", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

render_page_header(
    "Advanced QA/QC Tools",
    "Structured field and management tools for Lean Six Sigma, root cause analysis, concrete planning, inspection readiness, and corrective action control.",
    "Quality Engineering Toolkit",
)

st.markdown(
    """
<div class="tool-grid">
    <div class="tool-card"><div class="card-eyebrow">Lean Six Sigma</div><h3>DMAIC workflow</h3><p>Define, measure, analyse, improve, and control quality issues with accountable actions.</p></div>
    <div class="tool-card"><div class="card-eyebrow">Continuous Improvement</div><h3>PDCA cycle</h3><p>Plan, do, check, and act on quality improvements with clear owners and evidence.</p></div>
    <div class="tool-card"><div class="card-eyebrow">Root Cause</div><h3>5 Whys and fishbone</h3><p>Move beyond symptoms and capture evidence-based causes before closing NCRs.</p></div>
    <div class="tool-card"><div class="card-eyebrow">Concrete</div><h3>Volume and materials</h3><p>Estimate volume, waste allowance, cement bags, aggregate demand, and pour readiness.</p></div>
    <div class="tool-card"><div class="card-eyebrow">Risk</div><h3>RPN scoring</h3><p>Prioritise failure modes using severity, occurrence, and detection ratings.</p></div>
</div>
""",
    unsafe_allow_html=True,
)

tab_dmaic, tab_pdca, tab_rca, tab_concrete, tab_risk, tab_checklist = st.tabs(
    ["Lean Six Sigma", "PDCA", "Root Cause Analysis", "Concrete Calculator", "Risk Priority", "Inspection Readiness"]
)

with tab_dmaic:
    st.subheader("DMAIC Action Builder")
    c1, c2 = st.columns(2)
    with c1:
        problem = st.text_area("Define: problem statement", placeholder="Example: Repeated weld repair rate above project target.")
        metric = st.text_input("Measure: CTQ metric", placeholder="Repair rate %, NCR count, rejection rate...")
        baseline = st.number_input("Baseline value", min_value=0.0, value=0.0, step=0.1)
    with c2:
        target = st.number_input("Target value", min_value=0.0, value=0.0, step=0.1)
        owner = st.text_input("Process owner")
        due_date = st.date_input("Control review date")

    st.markdown("#### DMAIC summary")
    dmaic_df = pd.DataFrame(
        [
            ["Define", problem or "Not defined"],
            ["Measure", metric or "Not defined"],
            ["Analyse", "Validate causes using data, site observations, inspection records, and interviews."],
            ["Improve", "Assign corrective and preventive actions with owner, due date, and verification evidence."],
            ["Control", f"Review by {due_date} and monitor against target value {target:g}."],
        ],
        columns=["Phase", "Output"],
    )
    render_table(dmaic_df)
    if baseline and target:
        direction = "reduction" if target < baseline else "improvement"
        change = abs((baseline - target) / baseline) * 100
        st.metric(f"Required {direction}", f"{change:.1f}%")
    if owner:
        st.info(f"Accountable owner: {owner}")

with tab_pdca:
    st.subheader("PDCA Continuous Improvement Builder")
    p1, p2 = st.columns(2)
    with p1:
        improvement = st.text_area("Plan: improvement objective", placeholder="Example: Reduce concrete cube failure risk before next major pour.")
        current_gap = st.text_input("Current gap / baseline")
        planned_action = st.text_area("Do: trial action")
    with p2:
        check_method = st.text_area("Check: evidence and measurement method")
        act_decision = st.selectbox("Act: decision", ["Standardise", "Adjust and repeat", "Escalate", "Close after verification"])
        pdca_owner = st.text_input("Owner", key="pdca_owner")

    pdca_df = pd.DataFrame(
        [
            {"Cycle": "Plan", "Output": improvement or "Define the target, process gap, risk, and expected benefit."},
            {"Cycle": "Do", "Output": planned_action or "Run a controlled action or field trial with responsible persons."},
            {"Cycle": "Check", "Output": check_method or "Compare evidence against baseline, acceptance criteria, and CTQ targets."},
            {"Cycle": "Act", "Output": act_decision},
        ]
    )
    render_table(pdca_df)
    if current_gap:
        st.info(f"Baseline/gap to verify: {current_gap}")
    if pdca_owner:
        st.success(f"PDCA owner assigned: {pdca_owner}")

with tab_rca:
    st.subheader("Root Cause Analysis")
    st.caption("Move from the observed problem to a verified process or system cause; avoid personal blame statements.")
    with st.container(border=True):
        incident = st.text_area("Nonconformance / issue description")
        why_values = []
        for index in range(1, 6):
            why_values.append(st.text_input(f"Why {index}", key=f"why_{index}"))

    st.markdown("#### Fishbone categories")
    fishbone_left, fishbone_right = st.columns(2)
    fishbone = {
        "Manpower": fishbone_left.text_input("People / competency"),
        "Method": fishbone_left.text_input("Procedure / work method"),
        "Machine": fishbone_left.text_input("Equipment / tools"),
        "Material": fishbone_right.text_input("Material / consumables"),
        "Measurement": fishbone_right.text_input("Inspection / testing / calibration"),
        "Environment": fishbone_right.text_input("Weather / access / site condition"),
    }
    rca_df = pd.DataFrame(
        [{"Category": key, "Possible cause": value or "To be assessed"} for key, value in fishbone.items()]
    )
    render_table(rca_df)
    root_cause = next((item for item in reversed(why_values) if item), "")
    if root_cause:
        st.success(f"Likely root cause to verify: {root_cause}")
    elif incident:
        st.warning("Capture the 5 Whys to avoid closing the issue on symptoms only.")

with tab_concrete:
    st.subheader("Concrete Volume Calculator")
    basis_col, allowance_col = st.columns(2)
    with basis_col:
        shape = st.selectbox("Element type", ["Slab / rectangular footing", "Column / cylinder", "Wall / beam"])
    with allowance_col:
        waste = st.slider("Waste allowance (%)", min_value=0, max_value=20, value=5)

    if shape == "Column / cylinder":
        diameter_col, height_col = st.columns(2)
        diameter = diameter_col.number_input("Diameter (m)", min_value=0.0, value=0.6, step=0.05)
        height = height_col.number_input("Height (m)", min_value=0.0, value=3.0, step=0.1)
        volume = math.pi * (diameter / 2) ** 2 * height
    else:
        length_col, width_col, depth_col = st.columns(3)
        length = length_col.number_input("Length (m)", min_value=0.0, value=10.0, step=0.1)
        width = width_col.number_input("Width / thickness (m)", min_value=0.0, value=0.25, step=0.05)
        depth = depth_col.number_input("Depth / height (m)", min_value=0.0, value=0.3, step=0.05)
        volume = length * width * depth

    adjusted = volume * (1 + waste / 100)
    cement_col, guidance_col = st.columns([1, 2])
    with cement_col:
        cement_content = st.number_input("Cement content (kg/m3)", min_value=250, max_value=600, value=380, step=5)
    with guidance_col:
        st.info("Use the approved project mix design for cement content; this calculator is a planning aid, not a batching instruction.")
    cement_tonnes = adjusted * cement_content / 1000
    bags_50kg = cement_tonnes * 1000 / 50
    c1, c2, c3 = st.columns(3)
    c1.metric("Net concrete", f"{volume:,.2f} m3")
    c2.metric("With allowance", f"{adjusted:,.2f} m3")
    c3.metric("50 kg cement bags", f"{bags_50kg:,.0f}")
    st.caption("Use project-approved mix design values for final procurement and pour approval.")

with tab_risk:
    st.subheader("Failure Mode Risk Priority Number")
    failure_mode = st.text_input("Failure mode", placeholder="Example: Unapproved welding consumable used")
    severity_col, occurrence_col, detection_col = st.columns(3)
    severity = severity_col.slider("Severity", 1, 10, 7)
    occurrence = occurrence_col.slider("Occurrence", 1, 10, 4)
    detection = detection_col.slider("Detection difficulty", 1, 10, 5)
    rpn = severity * occurrence * detection
    band = "Low" if rpn < 80 else "Medium" if rpn < 200 else "High"
    st.metric("Risk Priority Number", rpn, band)
    st.progress(min(rpn / 1000, 1.0))
    if failure_mode:
        st.info(f"Recommended action: define prevention and detection controls for '{failure_mode}'.")

with tab_checklist:
    st.subheader("Inspection Readiness Checklist")
    checklist_left, checklist_right = st.columns(2)
    checks = {
        "Approved ITP and latest drawing available": checklist_left.checkbox("Approved ITP and latest drawing available"),
        "Material certificates and traceability verified": checklist_left.checkbox("Material certificates and traceability verified"),
        "Calibrated equipment available": checklist_left.checkbox("Calibrated equipment available"),
        "Qualified inspector / technician assigned": checklist_right.checkbox("Qualified inspector / technician assigned"),
        "Hold/witness points notified": checklist_right.checkbox("Hold/witness points notified"),
        "Acceptance criteria confirmed": checklist_right.checkbox("Acceptance criteria confirmed"),
    }
    score = sum(checks.values())
    st.metric("Readiness", f"{score}/{len(checks)}")
    if score == len(checks):
        st.success("Inspection is ready to proceed.")
    else:
        st.warning("Close all readiness gaps before release or client notification.")
