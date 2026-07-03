"""Tests for full check reporting."""
from tests.test_parser import _sample_psbt_b64, _sample_rawtx_hex


def test_score_returns_all_twelve_checks():
    from scorer import score

    report = score(_sample_psbt_b64())

    assert len(report.checks) == 12
    assert [check.heuristic_id for check in report.checks] == [
        "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11", "H13",
    ]


def test_failed_checks_match_findings():
    from scorer import score

    report = score(_sample_psbt_b64())
    finding_ids = {finding.heuristic_id for finding in report.findings}
    failed_check_ids = {check.heuristic_id for check in report.checks if check.status == "fail"}

    assert failed_check_ids == finding_ids


def test_failed_checks_carry_finding_detail_as_reason():
    from scorer import score

    report = score(_sample_psbt_b64())
    failed = [check for check in report.checks if check.status == "fail"]
    details = {finding.heuristic_id: finding.detail for finding in report.findings}

    assert failed
    for check in failed:
        assert check.reason == details[check.heuristic_id]


def test_missing_input_metadata_marks_checks_unavailable(monkeypatch):
    import scorer.parser as parser
    from scorer import score

    monkeypatch.setattr(
        parser,
        "get_tx_hex",
        lambda txid: (_ for _ in ()).throw(RuntimeError("lookup unavailable")),
    )

    report = score(_sample_rawtx_hex())
    checks = {check.heuristic_id: check for check in report.checks}

    assert checks["H1"].status == "unavailable"
    assert checks["H3"].status == "unavailable"
    assert checks["H6"].status == "unavailable"
    assert checks["H1"].reason == "Input script types unavailable"


def _block_all_lookups(monkeypatch):
    import scorer.lookup as lookup_mod

    def _fail(*args, **kwargs):
        raise AssertionError("network lookup attempted with lookup=False")

    monkeypatch.setattr(lookup_mod, "_request_with_fallback", _fail)


def test_score_as_rawtx_offline_makes_no_lookup_calls(monkeypatch):
    from scorer import score_as

    _block_all_lookups(monkeypatch)

    report = score_as(_sample_rawtx_hex(), input_type="rawtx", lookup=False)
    checks = {check.heuristic_id: check for check in report.checks}

    assert report.score is not None
    assert checks["H3"].status in ("skipped", "unavailable")
    assert checks["H4"].status in ("skipped", "unavailable")
    assert checks["H6"].status == "unavailable"


def test_score_as_psbt_offline_makes_no_lookup_calls(monkeypatch):
    from scorer import score_as

    _block_all_lookups(monkeypatch)

    report = score_as(_sample_psbt_b64(), input_type="psbt", lookup=False)

    assert report.score is not None
    assert report.input_count == 1


def test_score_as_rawtx_with_lookup_enriches_prevouts(monkeypatch):
    import scorer.parser as parser
    from tests.test_parser import _sample_prevtx_hex
    from scorer import score_as

    import scorer.heuristics.h3_address_reuse as h3
    import scorer.heuristics.h4_utxo_age as h4

    monkeypatch.setattr(parser, "get_tx_hex", lambda txid: _sample_prevtx_hex())
    monkeypatch.setattr(h3, "get_address_txs", lambda address: [])
    monkeypatch.setattr(h4, "get_utxo_block_height", lambda txid: None)

    report = score_as(_sample_rawtx_hex(), input_type="rawtx", lookup=True)
    checks = {check.heuristic_id: check for check in report.checks}

    assert checks["H6"].status in ("pass", "fail")
