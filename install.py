import os, sys, subprocess, logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(BASE_DIR, "artemis_venv")
LOG_FILE = os.path.join(BASE_DIR, "artemis_install.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

def run(cmd, label):
    logging.info(f"Starting: {label}")
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        logging.info(f"Done: {label}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed: {label}\n{e.stderr}")
        sys.exit(1)

logging.info("=== Artemis II Tracker — Installer ===")

if not os.path.exists(VENV_DIR):
    run(f"python3 -m venv {VENV_DIR}", "Create venv")

pip = os.path.join(VENV_DIR, "bin", "pip")
run(f"{pip} install --upgrade pip",          "Upgrade pip")
run(f"{pip} install streamlit plotly requests", "Install dependencies")

streamlit = os.path.join(VENV_DIR, "bin", "streamlit")
logging.info("=== Install complete ===")
logging.info(f"To launch the tracker, run:")
logging.info(f"  {streamlit} run app.py")
