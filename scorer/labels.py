import sqlite3
import json
from pathlib import Path

DB_PATH = Path.home() / ".utxo-privacy-scorer" / "labels.db"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS labels (
            txid TEXT, vout INTEGER, label TEXT,
            tag TEXT DEFAULT 'unknown',
            added_at TEXT, source TEXT,
            PRIMARY KEY (txid, vout)
        )
    """)
    con.commit()
    con.close()


def get_label(txid: str, vout: int) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT * FROM labels WHERE txid=? AND vout=?", (txid, vout)
    ).fetchone()
    con.close()
    if row:
        return dict(zip(["txid", "vout", "label", "tag", "added_at", "source"], row))
    return None


def get_all_labels() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT * FROM labels").fetchall()
    con.close()
    keys = ["txid", "vout", "label", "tag", "added_at", "source"]
    return [dict(zip(keys, row)) for row in rows]


def add_label(txid: str, vout: int, label: str, tag: str = "unknown", source: str = "user"):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR REPLACE INTO labels VALUES (?,?,?,?,datetime('now'),?)",
        (txid, vout, label, tag, source)
    )
    con.commit()
    con.close()


def import_sparrow(json_path: str) -> int:
    with open(json_path) as f:
        data = json.load(f)
    con = sqlite3.connect(DB_PATH)
    count = 0
    for key, label in data.items():
        txid, vout = key.rsplit(":", 1)
        con.execute(
            "INSERT OR REPLACE INTO labels VALUES (?,?,?,?,datetime('now'),'sparrow')",
            (txid, int(vout), label, "unknown")
        )
        count += 1
    con.commit()
    con.close()
    return count
