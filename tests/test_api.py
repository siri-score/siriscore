"""Tests for API error handling."""
from fastapi.testclient import TestClient

from api.main import app


def test_label_import_rejects_zero_label_file(tmp_path, monkeypatch):
    import scorer.labels as labels_mod

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    client = TestClient(app)
    response = client.post(
        "/labels/import",
        files={"file": ("bad.jsonl", b'{"hello":"world"}\n', "application/json")},
    )

    assert response.status_code == 400
    assert "No labels were imported" in response.json()["detail"]


def test_score_returns_only_matching_input_labels(tmp_path, monkeypatch):
    import scorer.labels as labels_mod
    from tests.test_parser import _sample_psbt_b64, P2WPKH_SCRIPT
    from scorer.parser import script_to_address

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()
    labels_mod.add_address_label(script_to_address(bytes.fromhex(P2WPKH_SCRIPT)), "Matching address")
    labels_mod.add_transaction_label("f" * 64, "Unrelated transaction", "tainted")

    client = TestClient(app)
    response = client.post("/score", json={"input": _sample_psbt_b64(), "input_type": "psbt"})
    labels = response.json()["labels"]

    assert response.status_code == 200
    assert len(labels) == 1
    assert labels[0]["label"] == "Matching address"
    assert labels[0]["in_inputs"] is True
