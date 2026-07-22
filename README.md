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
The companion API is available at http://localhost:8000. Interactive API
documentation is available only in development mode; it is disabled in production.

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
$env:QAQC_BOOTSTRAP_ADMIN_EMAIL="security-admin@example.com"
$env:QAQC_BOOTSTRAP_ADMIN_PASSWORD="use-a-unique-strong-password-here"
```

5. Migrate the existing users once, then run the app:

```bash
python database/migrate_users_to_mongodb.py
streamlit run app.py
```

On the first successful startup, remove `QAQC_BOOTSTRAP_ADMIN_PASSWORD` from
the environment or secrets store. The application never creates a predictable
default account and will fail closed until a strong bootstrap credential is supplied.

The migration preserves the existing password hashes. It refuses to overwrite a
non-empty MongoDB users collection unless `--force` is explicitly supplied.

For local Streamlit development, generate the Git-ignored secrets file from
the existing `.env` values:

```bash
python scripts/create_streamlit_secrets.py
```

Then add your email delivery credentials to `.streamlit/secrets.toml`. For
Gmail, enable 2-Step Verification on `fortunesundayske@gmail.com`, create a
Google App Password, and save the 16-character value as
`QAQC_GMAIL_APP_PASSWORD`. Do not use or store the normal Gmail password.
A sanitized reference is available at
`.streamlit/secrets.toml.example`; the populated file is never committed.
Gmail is used when both `QAQC_GMAIL_ADDRESS` and `QAQC_GMAIL_APP_PASSWORD` are
configured; otherwise the existing Exchange Online configuration is used.
These settings enable approval and customer-support email delivery.
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
AI support remains disabled unless `QAQC_ENABLE_AI_SUPPORT=true` is also set,
so project support messages are not sent to an external model unintentionally.
Set `QAQC_APP_URL` to the deployed dashboard URL to include a direct sign-in
link in each requestor's approval email.

Profile-photo changes are uploaded to Cloudinary and their secure URLs are
stored in each MongoDB user record, so photos follow the account across devices.
User activity is stored in MongoDB for the admin Activity Log and continuously
synced to the authenticated Cloudinary workbook
`qaqc-dashboard/activity-logs/QAQC_Activity_Log.xlsx`. The workbook contains
one worksheet per UTC date and uses event IDs to prevent duplicate rows.

The admin activity API exposes `GET /api/activity-logs` for paginated results and
`GET /api/activity-logs/csv` for the complete filtered CSV. Both accept inclusive
`start_date` and `end_date` values in `YYYY-MM-DD` format plus optional `username`,
`action`, and `result` filters. The list endpoint additionally accepts `page` and
`page_size` (maximum 100). Send the active dashboard session token as
`Authorization: Bearer <token>`. Only approved users with the exact `admin` role
are accepted; every other role receives HTTP 403.

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

## Production security

- Terminate TLS at a managed load balancer or reverse proxy; never expose ports
  8501 or 8000 directly to the internet. The Docker Compose defaults bind them
  to localhost for this reason.
- Set `QAQC_ALLOWED_HOSTS` to the exact API hostname and keep
  `QAQC_FORCE_HTTPS=true`. Production API docs are disabled and responses include
  no-store, anti-framing, content-type, referrer, permissions, CSP, and HSTS headers.
- Remote `mongodb://` connections must explicitly enable TLS; Atlas
  `mongodb+srv://` connections use TLS unless explicitly disabled. Restrict Atlas
  network access and use a least-privilege database user.
- Authentication sessions are server-side, expire after eight hours, and time
  out after two minutes of inactivity. A strict same-site browser-session cookie
  restores the session after navigation or a brief connection reset; it contains
  only a random credential, never a password, and is never placed in a URL. Keep
  `QAQC_COOKIE_SECURE=true` on HTTPS deployments. Five failed attempts lock an
  account for 15 minutes. Password hashes are upgraded to 600,000-iteration
  PBKDF2 on successful login.
- New support attachments and profile photos are content-validated, stored as
  authenticated Cloudinary assets, and exposed only through short-lived signed URLs.
- Prefer Docker/Kubernetes secret files by setting `SETTING_NAME_FILE=/run/secrets/...`;
  the app reads these without placing secret values in source files. Encrypt backups,
  rotate credentials, test restores, and retain audit logs according to company policy.
- Add organization-managed SSO with phishing-resistant MFA at the identity proxy
  for internet-facing deployments. Application controls do not replace MFA, WAF,
  endpoint security, vulnerability scanning, or database backup controls.
