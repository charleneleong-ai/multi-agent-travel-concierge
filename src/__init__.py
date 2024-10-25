from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path.cwd().parent
load_dotenv(f"{ROOT_DIR}/.env")
