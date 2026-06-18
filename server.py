from pathlib import Path
import subprocess
import sys
import webbrowser

ROOT = Path(__file__).resolve().parent
APP_FILE = ROOT / "app.py"
URL = "http://localhost:8501"

STREAMLIT_CMD = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    str(APP_FILE),
    "--server.port",
    "8501",
    "--server.headless",
    "true",
]


def main():
    if not APP_FILE.exists():
        raise FileNotFoundError(f"Streamlit app not found: {APP_FILE}")

    print(f"Starting QA/QC dashboard at {URL}")
    print("Launching Streamlit server...")
    try:
        webbrowser.open(URL, new=2)
    except Exception:
        pass

    process = subprocess.Popen(STREAMLIT_CMD, cwd=ROOT)
    try:
        process.wait()
    except KeyboardInterrupt:
        print("Stopping Streamlit server...")
        process.terminate()
        process.wait()


if __name__ == "__main__":
    main()
