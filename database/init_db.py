import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
from utils import load_master_data

DATA_FILE = ROOT_DIR / "data" / "QAQC_Master.xlsx"
DB_FILE = Path(__file__).parent / "qaqc_dashboard.db"
SCHEMA_FILE = Path(__file__).parent / "schema.sql"

if __name__ == "__main__":
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Master Excel file not found: {DATA_FILE}")
    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_FILE}")

    conn = sqlite3.connect(DB_FILE)
    with open(SCHEMA_FILE, "r", encoding="utf-8") as schema:
        conn.executescript(schema.read())

    sheets = load_master_data(DATA_FILE)
    for sheet_name, df in sheets.items():
        table_name = sheet_name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
        df.to_sql(table_name, conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_FILE}")
