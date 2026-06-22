import base64
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import auth
from utils import inject_global_ui, render_navigation, render_top_nav

BASE_DIR = Path(__file__).resolve().parents[1]
STANDARDS_DIR = BASE_DIR / "assets" / "standards"
PDF_EMBED_LIMIT_MB = 35


def clean_title(path):
    return path.stem.replace("_", " ").replace("-", " ").strip()


def infer_family(path):
    text = f"{path.parent.name} {path.name}".lower()
    if "dep" in text:
        return "DEP"
    if "gfs" in text:
        return "GFS"
    if "aws" in text or "weld" in text:
        return "AWS / Welding"
    if "aci" in text:
        return "ACI"
    if "astm" in text:
        return "ASTM"
    if "bs" in text or "en " in text or "eurocode" in text:
        return "BS / EN"
    if "cswip" in text or "ndt" in text or "radiographic" in text or "ultrasonic" in text:
        return "CSWIP / NDT"
    if "iso" in text:
        return "ISO"
    return "Reference"


def infer_discipline(path):
    text = path.name.lower()
    if any(word in text for word in ["concrete", "cement", "aci", "cube"]):
        return "Concrete"
    if any(word in text for word in ["road", "pavement", "asphalt", "cbr"]):
        return "Road Works"
    if any(word in text for word in ["soil", "earth", "geotechnical", "foundation", "subgrade"]):
        return "Civil / Earthworks"
    if any(word in text for word in ["weld", "aws", "brazing"]):
        return "Welding"
    if any(word in text for word in ["ndt", "radiographic", "ultrasonic", "penetrant", "magnetic", "tofd", "paut", "eddy"]):
        return "NDT"
    if any(word in text for word in ["piping", "pipe", "flange"]):
        return "Piping"
    if any(word in text for word in ["steel", "structure"]):
        return "Structural Steel"
    if any(word in text for word in ["electrical", "instrument", "lighting"]):
        return "Electrical / Instrumentation"
    return "General"


def discover_pdf_library():
    if not STANDARDS_DIR.exists():
        return []
    records = []
    for path in sorted(STANDARDS_DIR.rglob("*.pdf")):
        size_mb = path.stat().st_size / (1024 * 1024)
        category = path.parent.name if path.parent != STANDARDS_DIR else infer_family(path)
        records.append(
            {
                "Title": clean_title(path),
                "Category": category.replace("_", " ").title(),
                "Family": infer_family(path),
                "Discipline": infer_discipline(path),
                "Size MB": round(size_mb, 2),
                "Path": path,
                "Display": f"{clean_title(path)}  |  {infer_family(path)}  |  {round(size_mb, 1)} MB",
            }
        )
    return records


st.set_page_config(page_title="Standards Library", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

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

st.markdown('<div class="section-heading">Standards PDF Library</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Search, view, and download the available DEP, GFS, AWS, ACI, ASTM, BS/EN, ISO, CSWIP, NDT, concrete, civil, road works, welding, and piping references.</div>',
    unsafe_allow_html=True,
)
pdf_records = discover_pdf_library()
if not pdf_records:
    st.warning("No PDF documents found in the standards library folder.")
else:
    pdf_df = pd.DataFrame(pdf_records)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("PDF documents", len(pdf_df))
    p2.metric("Families", pdf_df["Family"].nunique())
    p3.metric("Disciplines", pdf_df["Discipline"].nunique())
    p4.metric("Library size", f"{pdf_df['Size MB'].sum():,.1f} MB")

    lib_col1, lib_col2, lib_col3 = st.columns([1.35, 1, 1])
    with lib_col1:
        pdf_search = st.text_input("Search PDF documents", placeholder="Try DEP, GFS, AWS, concrete, CWI, NDT, road works...")
    with lib_col2:
        pdf_family = st.selectbox("PDF family", ["All"] + sorted(pdf_df["Family"].unique().tolist()))
    with lib_col3:
        pdf_discipline = st.selectbox("PDF discipline", ["All"] + sorted(pdf_df["Discipline"].unique().tolist()))

    visible_pdf_df = pdf_df.copy()
    if pdf_search:
        search = pdf_search.lower()
        visible_pdf_df = visible_pdf_df[
            visible_pdf_df.apply(
                lambda row: search
                in " ".join(str(row[col]).lower() for col in ["Title", "Category", "Family", "Discipline"]),
                axis=1,
            )
        ]
    if pdf_family != "All":
        visible_pdf_df = visible_pdf_df[visible_pdf_df["Family"] == pdf_family]
    if pdf_discipline != "All":
        visible_pdf_df = visible_pdf_df[visible_pdf_df["Discipline"] == pdf_discipline]

    st.caption(f"{len(visible_pdf_df)} document(s) match the current filters.")
    if visible_pdf_df.empty:
        st.warning("No PDF document matches the selected filters.")
    else:
        selected_display = st.selectbox("Select PDF to view", visible_pdf_df["Display"].tolist())
        selected_pdf = visible_pdf_df[visible_pdf_df["Display"] == selected_display].iloc[0]
        pdf_path = selected_pdf["Path"]

        st.markdown(
            f"""
<div class="standard-card smooth-panel">
    <div class="card-eyebrow">{selected_pdf["Family"]} | {selected_pdf["Discipline"]}</div>
    <h3>{selected_pdf["Title"]}</h3>
    <p>Category: {selected_pdf["Category"]} | File size: {selected_pdf["Size MB"]} MB</p>
</div>
""",
            unsafe_allow_html=True,
        )

        if pdf_path.exists():
            pdf_bytes = pdf_path.read_bytes()
            st.download_button(
                "Download selected PDF",
                data=pdf_bytes,
                file_name=pdf_path.name,
                mime="application/pdf",
                use_container_width=True,
            )
            if selected_pdf["Size MB"] <= PDF_EMBED_LIMIT_MB:
                pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
                components.html(
                    f"""
<iframe
    src="data:application/pdf;base64,{pdf_b64}#toolbar=1&navpanes=1"
    width="100%"
    height="760"
    style="border: 1px solid rgba(148, 163, 184, 0.24); border-radius: 8px; background: white;"
></iframe>
""",
                    height=790,
                )
            else:
                st.info(
                    f"This PDF is larger than {PDF_EMBED_LIMIT_MB} MB, so it is available for download instead of inline preview to keep the dashboard responsive."
                )
        else:
            st.error(f"PDF not found: {pdf_path}")

        with st.expander("Show matching PDF table"):
            table_df = visible_pdf_df.drop(columns=["Path", "Display"])
            st.dataframe(table_df, use_container_width=True, hide_index=True)

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
        "DEP": "DEP 34.19.20.31-GEN concrete works, durability, curing, placement, testing, and records requirements",
        "BS": "BS EN 206 concrete, BS 8500 complementary UK guidance, BS EN 12350 fresh concrete testing, BS EN 12390 hardened concrete testing",
        "Inspection focus": "Mix approval, batch ticket, slump, temperature, cubes/cylinders, curing, pour card, repair records",
    },
    {
        "Discipline": "Road Works / Pavement",
        "ASTM": "ASTM D698/D1557 compaction, ASTM D6938 field density, ASTM C136 aggregate grading, asphalt and pavement tests where specified",
        "DEP": "DEP 34.13.20.31-GEN road works, pavement layers, subgrade, subbase, base course, surfacing, testing, and handover records",
        "BS": "BS 1377 soil testing, BS EN 13242 aggregates, BS EN 12697 asphalt test methods, BS 594987 asphalt laying awareness",
        "Inspection focus": "Subgrade approval, layer thickness, compaction, material grading, level/slope, drainage, test frequency, as-built records",
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
    {
        "Discipline": "Quality Management / PDCA",
        "ASTM": "ASTM quality-related test method control, inspection records, repeatability, traceability, and evidence discipline",
        "DEP": "DEP project quality management, audit findings, corrective actions, lessons learned, and management review expectations",
        "BS": "BS EN ISO 9001 quality management awareness, PDCA cycle, risk-based thinking, process control, and continual improvement",
        "Inspection focus": "Plan the improvement, do controlled actions, check evidence against CTQs, act by standardising or repeating the cycle",
    },
]

disciplines = ["All"] + sorted({item["Discipline"] for item in standards})
filter_col1, filter_col2, filter_col3 = st.columns([1.2, 1, 1])
with filter_col1:
    search_term = st.text_input("Search standards library", placeholder="Try concrete, welding, PDCA, NDT, handover...")
with filter_col2:
    selected = st.selectbox("Discipline", disciplines)
with filter_col3:
    family = st.selectbox("Standards family", ["All", "ASTM", "DEP", "BS"])


def matches_library_filters(item):
    haystack = " ".join(str(value) for value in item.values()).lower()
    if selected != "All" and item["Discipline"] != selected:
        return False
    if search_term and search_term.lower() not in haystack:
        return False
    if family != "All" and family.lower() not in item[family].lower():
        return False
    return True


filtered = [item for item in standards if matches_library_filters(item)]

m1, m2, m3 = st.columns(3)
m1.metric("Disciplines", len({item["Discipline"] for item in standards}))
m2.metric("Visible references", len(filtered))
m3.metric("Families", "ASTM / DEP / BS")

view_mode = st.radio("Library view", ["Cards", "Matrix"], horizontal=True, label_visibility="collapsed")

if not filtered:
    st.warning("No matching standards summary found. Try a broader search.")
elif view_mode == "Cards":
    for item in filtered:
        st.markdown(
            f"""
<div class="standard-card smooth-panel">
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
else:
    st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)

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
