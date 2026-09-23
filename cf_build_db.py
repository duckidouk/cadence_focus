import json
import sqlite3
from pathlib import Path

jlas = 'jlas-development-capital'
cadence = 'cadence-equity-partner'
scci = 'scci'
company_name = jlas
json_file_name = f"company_data_{company_name}-limited.json"
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "data" / "database" / "cf.db"

with open(DATA_DIR / json_file_name) as f:
    data = json.load(f)
print(type(data))

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

#cursor.execute(f"select * from {json_file_name}")
