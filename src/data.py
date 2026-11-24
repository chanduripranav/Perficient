from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "careconnect.db"
CSV_PATH = ROOT / "data" / "healthcare_prices.csv"
JSON_PATH = ROOT / "data" / "healthcare_prices.json"

CONTRACT_COLUMNS = [
    "record_id", "hospital_name", "city", "zip_code", "procedure_code",
    "procedure_name", "plan", "price", "source_url", "source_row",
    "last_updated", "is_demo",
]

PROCEDURES = {
    "73721": "MRI lower-extremity joint without contrast",
    "70551": "MRI brain without contrast",
    "74176": "CT abdomen and pelvis without contrast",
}

DEMO_HOSPITALS = [
    ("DEMO Parkland Memorial Hospital", "Dallas", "75235", 480, 630, 390),
    ("DEMO Methodist Richardson", "Richardson", "75082", 350, 710, 440),
    ("DEMO Baylor Plano", "Plano", "75093", 560, 520, 310),
    ("DEMO Medical City Dallas", "Dallas", "75230", 510, 590, 365),
    ("DEMO Texas Health Plano", "Plano", "75093", 395, 610, 340),
    ("DEMO UT Southwestern", "Dallas", "75390", 465, 575, 355),
    ("DEMO Methodist Mansfield", "Mansfield", "76063", 420, 665, 415),
]


def demo_records() -> pd.DataFrame:
    rows = []
    record_id = 1
    for hospital, city, zip_code, knee, brain, ct in DEMO_HOSPITALS:
        for code, price in (("73721", knee), ("70551", brain), ("74176", ct)):
            rows.append({
                "record_id": record_id,
                "hospital_name": hospital,
                "city": city,
                "zip_code": zip_code,
                "procedure_code": code,
                "procedure_name": PROCEDURES[code],
                "plan": "Blue Choice PPO",
                "price": float(price),
                "source_url": None,
                "source_row": None,
                "last_updated": None,
                "is_demo": True,
            })
            record_id += 1
    return pd.DataFrame(rows, columns=CONTRACT_COLUMNS)


def save_contract(df: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    df = df.copy()
    df["is_demo"] = df["is_demo"].astype(bool)
    df.to_csv(CSV_PATH, index=False)
    df.to_json(JSON_PATH, orient="records", indent=2)
    with sqlite3.connect(db_path) as conn:
        df.to_sql("healthcare_prices", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_code ON healthcare_prices(procedure_code)")


def load_records(db_path: Path = DB_PATH) -> pd.DataFrame:
    if not db_path.exists():
        save_contract(demo_records())
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query("SELECT * FROM healthcare_prices", conn)
        except pd.errors.DatabaseError:
            df = demo_records()
    return df


def query_records(procedure_code: str, live_only: bool = False, db_path: Path = DB_PATH) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        sql = """
        SELECT * FROM healthcare_prices
        WHERE procedure_code = ? AND plan = 'Blue Choice PPO'
          AND price > 0
        """
        params: list = [procedure_code]
        if live_only:
            sql += " AND is_demo = 0"
        sql += " ORDER BY price ASC"
        return pd.read_sql_query(sql, conn, params=params)


def add_live_records(df: pd.DataFrame, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Normalize already curated records and append or replace live records."""
    missing = set(CONTRACT_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    live = df.copy()
    live["record_id"] = range(1000, 1000 + len(live))
    live["is_demo"] = False
    live["procedure_code"] = live["procedure_code"].astype(str).str.zfill(5)
    live["price"] = pd.to_numeric(live["price"], errors="coerce")
    live = live[live["procedure_code"].isin(PROCEDURES.keys())]
    live = live[live["price"] > 0]
    live["plan"] = "Blue Choice PPO"
    save_contract(live)
    return live
