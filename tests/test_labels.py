"""Tests for SQLite label store."""
import json


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
