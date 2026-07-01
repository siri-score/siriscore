"""Tests for SQLite label store."""
import json
from pathlib import Path


def test_default_db_path_uses_tmp_on_vercel(monkeypatch):
    import scorer.labels as labels_mod

    monkeypatch.delenv("LABEL_DB_PATH", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.setenv("VERCEL", "1")

    assert labels_mod._default_db_path() == Path("/tmp") / "utxo-privacy-scorer" / "labels.db"


def test_default_db_path_honors_label_db_path(monkeypatch, tmp_path):
    import scorer.labels as labels_mod

    db_path = tmp_path / "custom-labels.db"
    monkeypatch.setenv("LABEL_DB_PATH", str(db_path))
    monkeypatch.setenv("VERCEL", "1")

    assert labels_mod._default_db_path() == db_path


def test_add_and_retrieve(tmp_path, monkeypatch):
    import scorer.labels as labels_mod
    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()
    labels_mod.add_label("abc123", 0, "Kraken withdrawal", "tainted")
    result = labels_mod.get_label("abc123", 0)
    assert result is not None
    assert result["tag"] == "tainted"
    assert result["label"] == "Kraken withdrawal"


def test_sparrow_import(tmp_path, monkeypatch):
    import scorer.labels as labels_mod
    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    sparrow_data = {"abc123:0": "Binance deposit", "def456:1": "coinjoin output"}
    json_path = tmp_path / "sparrow.json"
    json_path.write_text(json.dumps(sparrow_data))

    n = labels_mod.import_sparrow(str(json_path))
    assert n == 2
    assert labels_mod.get_label("abc123", 0) is not None


def test_sparrow_bip329_jsonl_imports_tx_address_and_utxo(tmp_path, monkeypatch):
    import scorer.labels as labels_mod

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    export = "\n".join([
        json.dumps({"type": "tx", "ref": "a" * 64, "label": "Exchange withdrawal", "tag": "tainted"}),
        json.dumps({"type": "addr", "ref": "bc1qexample", "label": "Cold storage", "tag": "clean"}),
        json.dumps({"type": "output", "ref": f"{'b' * 64}:1", "label": "Coinjoin output", "tag": "coinjoin"}),
    ])
    json_path = tmp_path / "sparrow-labels.jsonl"
    json_path.write_text(export)

    n = labels_mod.import_sparrow(str(json_path))

    assert n == 3
    assert labels_mod.get_input_label("a" * 64, 0)["label_type"] == "tx"
    assert labels_mod.get_input_label("unknown", 0, "bc1qexample")["label_type"] == "addr"
    assert labels_mod.get_label("b" * 64, 1)["label"] == "Coinjoin output"


def test_sparrow_single_line_bip329_import(tmp_path, monkeypatch):
    import scorer.labels as labels_mod

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    json_path = tmp_path / "single-line-sparrow.jsonl"
    json_path.write_text(json.dumps({"type": "addr", "ref": "bc1qsingle", "label": "Single line label"}))

    n = labels_mod.import_sparrow(str(json_path))

    assert n == 1
    assert labels_mod.get_input_label("unknown", 0, "bc1qsingle")["label"] == "Single line label"


def test_sparrow_structured_json_import(tmp_path, monkeypatch):
    import scorer.labels as labels_mod

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    export = {
        "transactions": [{"txid": "c" * 64, "label": "Transaction label", "tag": "tainted"}],
        "addresses": [{"address": "bc1qstructured", "label": "Address label"}],
        "utxos": [{"txid": "d" * 64, "vout": 2, "label": "UTXO label"}],
    }
    json_path = tmp_path / "sparrow-structured.json"
    json_path.write_text(json.dumps(export))

    n = labels_mod.import_sparrow(str(json_path))

    assert n == 3
    assert labels_mod.get_input_label("c" * 64, 0)["label"] == "Transaction label"
    assert labels_mod.get_input_label("unknown", 0, "bc1qstructured")["label"] == "Address label"
    assert labels_mod.get_label("d" * 64, 2)["label"] == "UTXO label"


def test_sparrow_import_returns_zero_for_unrecognized_file(tmp_path, monkeypatch):
    import scorer.labels as labels_mod

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    json_path = tmp_path / "not-labels.jsonl"
    json_path.write_text('{"hello":"world"}\n')

    assert labels_mod.import_sparrow(str(json_path)) == 0
