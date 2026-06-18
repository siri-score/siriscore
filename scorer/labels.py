import sqlite3
import json
from pathlib import Path
from json import JSONDecodeError

DB_PATH = Path.home() / ".utxo-privacy-scorer" / "labels.db"
SPARROW_FORMAT_TESTED = "Sparrow Wallet v1.8+ BIP329 JSONL label export"


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS labels (
            txid TEXT, vout INTEGER, label TEXT,
            tag TEXT DEFAULT 'unknown',
            added_at TEXT, source TEXT,
            label_type TEXT DEFAULT 'utxo',
            ref TEXT,
            address TEXT,
            PRIMARY KEY (txid, vout)
        )
    """)
    _ensure_column(con, "label_type", "TEXT DEFAULT 'utxo'")
    _ensure_column(con, "ref", "TEXT")
    _ensure_column(con, "address", "TEXT")
    con.commit()
    con.close()


def _ensure_column(con, name: str, ddl: str) -> None:
    columns = {row[1] for row in con.execute("PRAGMA table_info(labels)").fetchall()}
    if name not in columns:
        con.execute(f"ALTER TABLE labels ADD COLUMN {name} {ddl}")


def get_label(txid: str, vout: int) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    row = _fetch_label(
        con,
        "SELECT * FROM labels WHERE label_type='utxo' AND txid=? AND vout=?",
        (txid, vout),
    )
    con.close()
    return row


def get_input_label(txid: str, vout: int, address: str | None = None) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    record = _fetch_label(
        con,
        "SELECT * FROM labels WHERE label_type='utxo' AND txid=? AND vout=?",
        (txid, vout),
    )
    if record is None:
        record = _fetch_label(
            con,
            "SELECT * FROM labels WHERE label_type='tx' AND txid=?",
            (txid,),
        )
    if record is None and address:
        record = _fetch_label(
            con,
            "SELECT * FROM labels WHERE label_type='addr' AND address=?",
            (address,),
        )
    con.close()
    return record


def get_all_labels() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT * FROM labels").fetchall()
    keys = _label_keys(con)
    con.close()
    return [dict(zip(keys, row)) for row in rows]


def add_label(txid: str, vout: int, label: str, tag: str = "unknown", source: str = "user"):
    add_utxo_label(txid, vout, label, tag, source)


def add_utxo_label(txid: str, vout: int, label: str, tag: str = "unknown", source: str = "user"):
    con = sqlite3.connect(DB_PATH)
    ref = f"{txid}:{vout}"
    con.execute(
        """
        INSERT OR REPLACE INTO labels
        (txid, vout, label, tag, added_at, source, label_type, ref, address)
        VALUES (?,?,?,?,datetime('now'),?,?,?,NULL)
        """,
        (txid, vout, label, tag, source, "utxo", ref)
    )
    con.commit()
    con.close()


def add_transaction_label(txid: str, label: str, tag: str = "unknown", source: str = "sparrow"):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT OR REPLACE INTO labels
        (txid, vout, label, tag, added_at, source, label_type, ref, address)
        VALUES (?,NULL,?,?,datetime('now'),?,'tx',?,NULL)
        """,
        (txid, label, tag, source, txid)
    )
    con.commit()
    con.close()


def add_address_label(address: str, label: str, tag: str = "unknown", source: str = "sparrow"):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """
        INSERT INTO labels
        (txid, vout, label, tag, added_at, source, label_type, ref, address)
        VALUES (NULL,NULL,?,?,datetime('now'),?,'addr',?,?)
        """,
        (label, tag, source, address, address)
    )
    con.commit()
    con.close()


def import_sparrow(json_path: str) -> int:
    with open(json_path) as f:
        contents = f.read()

    labels = _parse_label_export(contents)
    count = 0
    for record in labels:
        if record["type"] == "utxo":
            add_utxo_label(record["txid"], record["vout"], record["label"], record["tag"], "sparrow")
        elif record["type"] == "tx":
            add_transaction_label(record["txid"], record["label"], record["tag"], "sparrow")
        elif record["type"] == "addr":
            add_address_label(record["address"], record["label"], record["tag"], "sparrow")
        count += 1
    return count


def _fetch_label(con, sql: str, params: tuple) -> dict | None:
    row = con.execute(sql, params).fetchone()
    if row is None:
        return None
    return dict(zip(_label_keys(con), row))


def _label_keys(con) -> list[str]:
    return [row[1] for row in con.execute("PRAGMA table_info(labels)").fetchall()]


def _parse_label_export(contents: str) -> list[dict]:
    stripped = contents.strip()
    if not stripped:
        return []

    try:
        data = json.loads(stripped)
        return [record for record in _parse_json_export(data) if record]
    except JSONDecodeError:
        return _parse_jsonl_export(stripped)


def _parse_json_export(data) -> list[dict]:
    if isinstance(data, dict) and {"type", "ref", "label"}.issubset(data):
        return _records_from_section([data], None)

    if isinstance(data, dict) and _looks_like_legacy_utxo_map(data):
        return [record for key, label in data.items() if label and (record := _utxo_record(key, label))]

    records = []
    if isinstance(data, dict):
        for key in ("transactions", "txs"):
            records.extend(_records_from_section(data.get(key), "tx"))
        for key in ("addresses", "addrs"):
            records.extend(_records_from_section(data.get(key), "addr"))
        for key in ("utxos", "outputs", "coins"):
            records.extend(_records_from_section(data.get(key), "utxo"))
        for key in ("labels", "items"):
            records.extend(_records_from_section(data.get(key), None))
    elif isinstance(data, list):
        records.extend(_records_from_section(data, None))
    return records


def _parse_jsonl_export(contents: str) -> list[dict]:
    records = []
    for line in contents.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.extend(_records_from_section([json.loads(line)], None))
        except JSONDecodeError:
            continue
    return records


def _looks_like_legacy_utxo_map(data: dict) -> bool:
    return bool(data) and all(isinstance(k, str) and ":" in k and isinstance(v, str) for k, v in data.items())


def _records_from_section(section, default_type: str | None) -> list[dict]:
    if section is None:
        return []
    if isinstance(section, dict):
        return [_record_from_key_value(key, value, default_type) for key, value in section.items()]
    if isinstance(section, list):
        return [record for item in section if (record := _record_from_item(item, default_type))]
    return []


def _record_from_key_value(key: str, value, default_type: str | None) -> dict | None:
    label = value.get("label") if isinstance(value, dict) else value
    item = {"type": default_type, "ref": key, "label": label}
    if isinstance(value, dict):
        item.update(value)
        item.setdefault("ref", key)
    return _record_from_item(item, default_type)


def _record_from_item(item, default_type: str | None) -> dict | None:
    if not isinstance(item, dict):
        return None
    label = item.get("label")
    if not label:
        return None

    label_type = (item.get("type") or default_type or "").lower()
    ref = item.get("ref") or item.get("reference") or item.get("txid") or item.get("address")
    tag = item.get("tag", "unknown")

    if label_type in ("output", "input", "utxo", "coin"):
        if (ref is None or ":" not in str(ref)) and item.get("txid") and item.get("vout") is not None:
            ref = f"{item['txid']}:{item['vout']}"
        return _utxo_record(ref, label, tag)
    if label_type in ("tx", "transaction"):
        return {"type": "tx", "txid": ref, "label": label, "tag": tag} if ref else None
    if label_type in ("addr", "address"):
        return {"type": "addr", "address": ref, "label": label, "tag": tag} if ref else None
    return None


def _utxo_record(ref: str, label: str, tag: str = "unknown") -> dict | None:
    if not ref or ":" not in ref:
        return None
    txid, vout = ref.rsplit(":", 1)
    try:
        parsed_vout = int(vout)
    except ValueError:
        return None
    return {"type": "utxo", "txid": txid, "vout": parsed_vout, "label": label, "tag": tag}
