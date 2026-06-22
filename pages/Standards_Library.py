import pandas as pd
import streamlit as st

from auth import login, render_user_sidebar
from utils import inject_global_ui, render_top_nav


st.set_page_config(page_title="Standards Library", layout="wide")
inject_global_ui()

if not login():
    st.stop()

render_top_nav()
render_user_sidebar()

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Controlled reference map</div>
    <h1>ASTM, DEP, and BS Standards by Discipline</h1>
    <p>A discipline-based guide for common construction QA/QC references. Use this page as a navigation and awareness tool; always verify the latest project contract, client specification, and licensed standard before acceptance decisions.</p>
</div>
""",
    unsafe_allow_html=True,
)

standards = [
    {
        "Discipline": "Civil / Earthworks",
        "ASTM": "ASTM D698/D1557 compaction, ASTM D4318 Atterberg limits, ASTM D6938 field density awareness",
        "DEP": "DEP civil engineering and earthworks requirements, project-specific site preparation and backfill practices",
        "BS": "BS 1377 soil testing, BS 5930 ground investigation, BS EN 1997 geotechnical design",
        "Inspection focus": "Approved fill, layer thickness, moisture control, compaction results, survey levels, hold points",
    },
    {
        "Discipline": "Concrete",
        "ASTM": "ASTM C31 specimens, ASTM C39 compression, ASTM C143 slump, ASTM C150 cement, ASTM C94 ready-mix awareness",
        "DEP": "DEP concrete works, durability, curing, placement, testing, and records requirements",
        "BS": "BS EN 206 concrete, BS 8500 complementary UK guidance, BS EN 12350 fresh concrete testing, BS EN 12390 hardened concrete testing",
        "Inspection focus": "Mix approval, batch ticket, slump, temperature, cubes/cylinders, curing, pour card, repair records",
    },
    {
        "Discipline": "Rebar / Structural Steel",
        "ASTM": "ASTM A615 reinforcement, ASTM A706 weldable reinforcement, ASTM A36/A572 structural steel awareness",
        "DEP": "DEP structural steelwork and reinforcement control requirements",
        "BS": "BS 4449 reinforcing steel, BS 8666 bar scheduling, BS EN 1090 steel execution",
        "Inspection focus": "Material traceability, mill certificates, bar spacing, laps, cover, bolt/weld records, coating condition",
    },
    {
        "Discipline": "Piping",
        "ASTM": "ASTM material specifications for pipe, fittings, flanges, gaskets, and bolting as applicable",
        "DEP": "DEP piping classes, fabrication, installation, pressure testing, reinstatement, and mechanical completion",
        "BS": "BS EN 13480 metallic industrial piping, BS EN 10204 inspection documents",
        "Inspection focus": "Material PMI, fit-up, weld maps, NDE status, supports, pressure test packs, flange management",
    },
    {
        "Discipline": "Welding",
        "ASTM": "ASTM material and filler metal references where specified by project code",
        "DEP": "DEP welding, PWHT, welder qualification, consumable control, repair, and traceability requirements",
        "BS": "BS EN ISO 15614 procedure qualification, BS EN ISO 9606 welder qualification, BS EN ISO 5817 imperfection levels",
        "Inspection focus": "WPS/PQR, welder continuity, consumable issue, preheat, interpass, visual inspection, repair rate",
    },
    {
        "Discipline": "NDT",
        "ASTM": "ASTM E165 penetrant, ASTM E709 magnetic particle, ASTM E94/E1742 radiography awareness, ASTM E797 ultrasonic thickness",
        "DEP": "DEP NDE extent, technique approval, personnel qualification, reporting, and acceptance requirements",
        "BS": "BS EN ISO 9712 personnel qualification, BS EN ISO 17635 NDT of welds, BS EN ISO 17636 radiography, BS EN ISO 17640 UT",
        "Inspection focus": "Technique sheet, calibration, qualified operator, coverage, sensitivity, report review, traceability",
    },
    {
        "Discipline": "Coating / Painting",
        "ASTM": "ASTM D4417 profile, ASTM D4541 pull-off, ASTM D7091 dry film thickness, ASTM D4285 compressed air cleanliness",
        "DEP": "DEP protective coating systems, surface preparation, environmental controls, application, holiday testing",
        "BS": "BS EN ISO 8501 surface cleanliness, BS EN ISO 8502 contaminants, BS EN ISO 8503 profile, BS EN ISO 12944 corrosion protection",
        "Inspection focus": "Surface prep, dew point, salt test, stripe coat, DFT, adhesion, curing, repair mapping",
    },
    {
        "Discipline": "Electrical / Instrumentation",
        "ASTM": "ASTM material references for cables, insulation, and supports where contractually specified",
        "DEP": "DEP electrical and instrumentation installation, loop checks, calibration, testing, and commissioning records",
        "BS": "BS 7671 wiring regulations awareness, BS EN 60079 hazardous area equipment, BS EN 61511 SIS awareness",
        "Inspection focus": "Cable tests, glanding, earthing, calibration certificates, loop folders, Ex inspection, punch closure",
    },
    {
        "Discipline": "Documentation / Handover",
        "ASTM": "ASTM test reports and material certificates tied to applicable technical standards",
        "DEP": "DEP quality records, MDR, certification dossier, inspection release, and mechanical completion requirements",
        "BS": "BS EN 10204 certificate types, BS 10008 evidential weight of electronic records awareness",
        "Inspection focus": "ITR completeness, traceability matrix, as-built records, NCR closeout, signed test packs, dossier index",
    },
]

disciplines = ["All"] + sorted({item["Discipline"] for item in standards})
selected = st.selectbox("Filter by discipline", disciplines)
filtered = [item for item in standards if selected == "All" or item["Discipline"] == selected]

for item in filtered:
    st.markdown(
        f"""
<div class="standard-card">
    <div class="card-eyebrow">{item["Discipline"]}</div>
    <h3>Inspection and acceptance reference summary</h3>
    <p><strong>ASTM:</strong> {item["ASTM"]}</p>
    <p><strong>DEP:</strong> {item["DEP"]}</p>
    <p><strong>BS:</strong> {item["BS"]}</p>
    <p><strong>Inspection focus:</strong> {item["Inspection focus"]}</p>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-heading">Standards Matrix</div>', unsafe_allow_html=True)
st.dataframe(pd.DataFrame(standards), use_container_width=True, hide_index=True)

st.markdown('<div class="section-heading">Controlled Use Rules</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="security-card">
    <h3>International project control</h3>
    <p>Do not use summaries as acceptance criteria. Acceptance must follow the contract hierarchy: project specification, client DEP or equivalent, governing code, approved drawings, approved ITP, approved procedure, and latest licensed standard revision.</p>
</div>
""",
    unsafe_allow_html=True,
)
