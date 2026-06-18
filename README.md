# Evomec QA/QC Executive Dashboard

A modern enterprise-grade QA/QC management dashboard for construction projects, built with Streamlit, Plotly, Pandas, and SQLite.

## Features

- Executive dashboard with KPI cards, trend charts, heat maps, and performance ranking
- Project-level modules for Daily Reports, ITR, NCR, OBS, Concrete, Audits, Surveillance, Documents, Lessons Learned, Defects/Rework, CTQ, Lean Six Sigma analytics, and management summary
- Global filters for project, discipline, date range, status, month, and year
- Export management reports to Excel and PDF
- Responsive layout, dark/light theme toggle, automatic refresh support

## Folder Structure

```
QAQC_Dashboard/
├── app.py
├── database/
│   ├── schema.sql
│   └── init_db.py
├── data/
│   └── QAQC_Master.xlsx
├── pages/
│   ├── Executive_Dashboard.py
│   ├── Daily_Reports.py
│   ├── ITR_Tracker.py
│   ├── NCR_Tracker.py
│   ├── OBS_Tracker.py

## Docker (optional, recommended for quick preview)

Build the Docker image and run the container (this will generate the sample Excel and initialize the SQLite DB at image build time):

```bash
cd "C:\Users\evome\Downloads\New folder (2)\QAQC_Dashboard"
docker build -t evomec-qaqc-dashboard .
docker run -p 8501:8501 --rm --name evomec-qaqc evomec-qaqc-dashboard
```

Or use Docker Compose:

```bash
docker-compose up --build
```

Then open http://localhost:8501 in your browser to view the dashboard.

Notes:
- The Docker image runs `sample_data.py` and `database/init_db.py` at build time to create `data/QAQC_Master.xlsx` and the SQLite DB.
- If you map a host volume over the container (`-v .:/app`), it will replace files created during build.
│   ├── Concrete_Tracker.py
│   ├── Audit_Surveillance.py
│   ├── Document_Status.py
│   ├── Lessons_Learned.py
│   ├── Project_Scorecard.py
│   ├── Defect_Rework_Tracker.py
├── assets/
│   └── company_logo.png
├── requirements.txt
└── README.md
```

## Installation

1. Install Python 3.11+.
2. Create a virtual environment:

```bash
python -m venv .venv
.\.venv\Scripts\activate
```

3. Install requirements:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
streamlit run app.py
```

## Data Source

Place the QAQC Excel workbook at `data/QAQC_Master.xlsx`. Use the provided template and sample data to start.

## Database

A SQLite schema is available at `database/schema.sql`. Use `database/init_db.py` to generate or refresh the SQLite database from the master Excel file.

## Notes

- The app reads from `data/QAQC_Master.xlsx` on startup.
- Use the sidebar filters to explore projects, disciplines, time periods, and status categories.
- Export buttons produce management-level Excel and PDF reports.
