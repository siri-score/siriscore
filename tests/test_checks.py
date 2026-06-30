"""Tests for full check reporting."""
from tests.test_parser import _sample_psbt_b64, _sample_rawtx_hex


def test_score_returns_all_eleven_checks():
    from scorer import score

    report = score(_sample_psbt_b64())

    assert len(report.checks) == 11
    assert [check.heuristic_id for check in report.checks] == [
        "H1", "H2", "H3", "H4", "H5", "H6", "H7", "H8", "H9", "H10", "H11",
    ]


def test_failed_checks_match_findings():
    from scorer import score

    report = score(_sample_psbt_b64())
    finding_ids = {finding.heuristic_id for finding in report.findings}
    failed_check_ids = {check.heuristic_id for check in report.checks if check.status == "fail"}

    assert failed_check_ids == finding_ids


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
