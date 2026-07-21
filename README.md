# Evomec QA/QC Executive Dashboard

A modern enterprise-grade QA/QC management dashboard for construction projects, built with Streamlit, Plotly, Pandas, and SQLite.

## Features

- Executive dashboard with KPI cards, trend charts, heat maps, and performance ranking
- Project-level modules for Daily Reports, ITR, NCR, OBS, Concrete, Audits, Surveillance, Documents, Lessons Learned, Defects/Rework, CTQ, Lean Six Sigma analytics, and management summary
- Global filters for project, discipline, date range, status, month, and year
- Export management reports to Excel and PDF
- Responsive layout, dark/light theme toggle, automatic refresh support
- MongoDB-backed user accounts and customer-support tickets
- Approval and support email notifications through Exchange Online / Microsoft Graph
- Admin-only calibration status, completed-date, certificate, and next-due updates synchronized to Cloudinary and Excel
- Automatic sign-out after two minutes without activity
- Interactive support chat with optional AI first response and live-admin escalation
- Cloudinary-backed support attachments and profile photos referenced from MongoDB

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

4. Set MongoDB credentials (PowerShell):

```powershell
$env:MONGODB_URI="mongodb+srv://USERNAME:PASSWORD@HOST/?retryWrites=true&w=majority"
$env:MONGODB_DATABASE="qaqc_dashboard"
```

5. Migrate the existing users once, then run the app:

```bash
python database/migrate_users_to_mongodb.py
streamlit run app.py
```

The migration preserves the existing password hashes. It refuses to overwrite a
non-empty MongoDB users collection unless `--force` is explicitly supplied.

For local Streamlit development, generate the Git-ignored secrets file from
the existing `.env` values:

```bash
python scripts/create_streamlit_secrets.py
```

Then add the three Azure application values still marked as missing to
`.streamlit/secrets.toml`. A sanitized reference is available at
`.streamlit/secrets.toml.example`; the populated file is never committed.
These Exchange Online settings enable approval and customer-support email delivery.
The Azure application needs Microsoft Graph `Mail.Send` application permission
with administrator consent. Support tickets are saved to MongoDB even when
Exchange is not configured.

For Streamlit Cloud, copy the same key/value pairs into **App settings →
Secrets** using TOML syntax. At minimum the deployed app requires:

```toml
MONGODB_URI = "mongodb+srv://USER:PASSWORD@HOST/?retryWrites=true&w=majority"
MONGODB_DATABASE = "qaqc_dashboard"
```

An `mongodb+srv://` URI must contain exactly one Atlas hostname. If using a
comma-separated Atlas seed list, use the `mongodb://` scheme instead. The app
normalizes this common scheme mismatch and shows a safe configuration message
for invalid credentials, network timeouts, and malformed URIs.

Add `CLOUDINARY_URL`, `OPENAI_API_KEY`, and the `QAQC_EXCHANGE_*` values there
to enable cloud uploads, AI support, and Exchange email notifications in
production.
Set `QAQC_APP_URL` to the deployed dashboard URL to include a direct sign-in
link in each requestor's approval email.

Profile-photo changes are uploaded to Cloudinary and their secure URLs are
stored in each MongoDB user record, so photos follow the account across devices.
User activity is stored in MongoDB for the admin Activity Log and continuously
synced to the authenticated Cloudinary workbook
`qaqc-dashboard/activity-logs/QAQC_Activity_Log.xlsx`. The workbook contains
one worksheet per UTC date and uses event IDs to prevent duplicate rows.

The six page-background assets are stored under
`qaqc-dashboard/backgrounds/` in Cloudinary. To republish the local fallback
copies, run:

```bash
python scripts/upload_page_backgrounds.py
```

To upload a timestamped backup of the dashboard application files, run:

```bash
python scripts/upload_dashboard_backup.py
```

The authenticated backup deliberately excludes secrets, account/profile data,
runtime/temp files, local databases, and the entire `assets/standards` folder
containing standards PDFs. Validate the backup selection without uploading by
adding `--dry-run`.
To migrate legacy local profile images once, run:

```bash
python scripts/migrate_profile_photos.py
```

## Cloud master workbook

The dashboard prefers the versioned Cloudinary copy of `QAQC_Master.xlsx` and
uses the repository file only as an offline fallback. After editing the workbook
locally, publish it with:

```bash
python scripts/upload_master_workbook.py
```

The deployed dashboard checks Cloudinary for a new workbook version every 60
seconds. Override the default asset only when needed with
`QAQC_MASTER_WORKBOOK_PUBLIC_ID`.

Admin concrete-volume entries update the `Concrete Tracker` sheet in this
Cloudinary workbook. Existing project names are reused case-insensitively, and
new projects are added once to `Project Register`.

## Data Source

Place the QAQC Excel workbook at `data/QAQC_Master.xlsx`. Use the provided template and sample data to start.

## Database

A SQLite schema is available at `database/schema.sql`. Use `database/init_db.py` to generate or refresh the SQLite database from the master Excel file.

## Notes

- The app reads from `data/QAQC_Master.xlsx` on startup.
- Use the sidebar filters to explore projects, disciplines, time periods, and status categories.
- Export buttons produce management-level Excel and PDF reports.
