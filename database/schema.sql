PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project_register (
    Project TEXT PRIMARY KEY,
    Discipline TEXT,
    Project_Manager TEXT,
    Location TEXT,
    Start_Date DATE,
    End_Date DATE,
    Status TEXT
);

CREATE TABLE IF NOT EXISTS daily_reports (
    Report_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Project TEXT,
    Discipline TEXT,
    Report_Date DATE,
    Summary TEXT,
    Status TEXT
);

CREATE TABLE IF NOT EXISTS itr_log (
    ITR_ID TEXT PRIMARY KEY,
    Project TEXT,
    Discipline TEXT,
    Activity TEXT,
    Status TEXT,
    Inspector TEXT,
    Date DATE
);

CREATE TABLE IF NOT EXISTS ncr_log (
    NCR_ID TEXT PRIMARY KEY,
    Project TEXT,
    Discipline TEXT,
    Description TEXT,
    Date_Raised DATE,
    Due_Date DATE,
    Status TEXT,
    Responsible_Person TEXT,
    Aging INTEGER
);

CREATE TABLE IF NOT EXISTS obs_log (
    OBS_ID TEXT PRIMARY KEY,
    Project TEXT,
    Status TEXT,
    Responsible_Person TEXT,
    Due_Date DATE,
    Date_Raised DATE
);

CREATE TABLE IF NOT EXISTS concrete_tracker (
    Pour_ID TEXT PRIMARY KEY,
    Project TEXT,
    Date DATE,
    Location TEXT,
    Volume REAL
);

CREATE TABLE IF NOT EXISTS audit_register (
    Audit_ID TEXT PRIMARY KEY,
    Project TEXT,
    Planned_Date DATE,
    Actual_Date DATE,
    Status TEXT,
    Auditor TEXT
);

CREATE TABLE IF NOT EXISTS surveillance_register (
    Surveillance_ID TEXT PRIMARY KEY,
    Project TEXT,
    Planned_Date DATE,
    Actual_Date DATE,
    Status TEXT,
    Inspector TEXT
);

CREATE TABLE IF NOT EXISTS document_register (
    Document_ID TEXT PRIMARY KEY,
    Project TEXT,
    Document_Type TEXT,
    Status TEXT,
    Revision TEXT,
    Issue_Date DATE,
    Due_Date DATE
);

CREATE TABLE IF NOT EXISTS lessons_learned (
    Lesson_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Project TEXT,
    Category TEXT,
    Lesson TEXT,
    Impact TEXT,
    Recommendation TEXT,
    Date_Logged DATE
);

CREATE TABLE IF NOT EXISTS defect_rework_log (
    Defect_ID TEXT PRIMARY KEY,
    Project TEXT,
    Discipline TEXT,
    Area_Location TEXT,
    Description TEXT,
    Root_Cause TEXT,
    Responsible_Contractor TEXT,
    Date_Identified DATE,
    Date_Closed DATE,
    Status TEXT,
    Rework_Cost REAL,
    Rework_Manhours REAL,
    Impact_Category TEXT,
    Preventive_Action TEXT
);

CREATE TABLE IF NOT EXISTS ctq_log (
    CTQ_ID TEXT PRIMARY KEY,
    Project TEXT,
    Discipline TEXT,
    Activity TEXT,
    CTQ_Description TEXT,
    Acceptance_Criteria TEXT,
    Specification_Reference TEXT,
    Inspection_Method TEXT,
    Frequency TEXT,
    Target_Value TEXT,
    Actual_Value TEXT,
    Status TEXT,
    Date DATE,
    Responsible_Inspector TEXT
);
