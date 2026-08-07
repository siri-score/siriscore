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


def test_score_defaults_to_no_network_lookup(tmp_path, monkeypatch):
    import scorer.labels as labels_mod
    import scorer.lookup as lookup_mod
    from tests.test_parser import _sample_rawtx_hex

    monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
    labels_mod.init_db()

    def _fail(*args, **kwargs):
        raise AssertionError("network call attempted on default /score request")

    monkeypatch.setattr(lookup_mod, "_request_with_fallback", _fail)

    client = TestClient(app)
    response = client.post("/score", json={"input": _sample_rawtx_hex(), "input_type": "rawtx"})

    assert response.status_code == 200
    checks = {c["id"]: c["status"] for c in response.json()["checks"]}
    assert checks["H3"] in ("skipped", "unavailable")
    assert checks["H4"] in ("skipped", "unavailable")


_EXPECTED_HEURISTIC_IDS = {
    "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8",
    "H9", "H10", "H11", "H13", "H14", "H15",
}


def test_list_heuristics_returns_200_and_all_ids():
    client = TestClient(app)
    response = client.get("/heuristics")

    assert response.status_code == 200
    heuristics = response.json()["heuristics"]
    assert {h["id"] for h in heuristics} == _EXPECTED_HEURISTIC_IDS


def test_list_heuristics_entries_match_schema():
    client = TestClient(app)
    response = client.get("/heuristics")
    heuristics = response.json()["heuristics"]

    expected_keys = {
        "id", "name", "severity", "weight",
        "requires_network", "description", "suggestion",
    }
    for h in heuristics:
        assert set(h.keys()) == expected_keys
        assert isinstance(h["id"], str)
        assert isinstance(h["name"], str) and h["name"]
        assert h["severity"] in ("critical", "warning", "info")
        assert isinstance(h["weight"], int)
        assert isinstance(h["requires_network"], bool)
        assert isinstance(h["description"], str) and h["description"]
        assert isinstance(h["suggestion"], str) and h["suggestion"]


def test_list_heuristics_flags_network_dependent_ids():
    client = TestClient(app)
    response = client.get("/heuristics")
    by_id = {h["id"]: h for h in response.json()["heuristics"]}

    assert by_id["H3"]["requires_network"] is True
    assert by_id["H4"]["requires_network"] is True
    assert by_id["H1"]["requires_network"] is False


def test_list_heuristics_requires_no_request_body():
    client = TestClient(app)
    response = client.get("/heuristics")

    assert response.status_code == 200
    assert response.request.content == b""


def test_score_returns_only_matching_input_labels(tmp_path, monkeypatch):
    import scorer.labels as labels_mod
    from scorer.parser import script_to_address
    from tests.test_parser import P2WPKH_SCRIPT, _sample_psbt_b64

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
