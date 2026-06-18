"""Tests for CLI exit codes and --json / --fail-below flags."""
import json
from unittest.mock import patch


from scorer.report import Report


def _make_report(score=80, findings=None, checks=None):
    return Report(
        score=score,
        findings=findings or [],
        checks=checks or [],
        input_count=1,
        output_count=2,
        psbt_version=0,
    )


def _run_cli(*args):
    """Run main() with the given argv and return SystemExit code (None = 0)."""
    from cli import main
    with patch("sys.argv", ["btc-privacy-check", *args]):
        try:
            main()
            return 0
        except SystemExit as exc:
            return exc.code


class TestFailBelow:
    def test_exits_0_when_score_meets_threshold(self, capsys):
        with patch("cli.score", return_value=_make_report(score=75)):
            code = _run_cli("--psbt", "cHNidP8BA", "--fail-below", "60")
        assert code == 0

    def test_exits_1_when_score_below_threshold(self, capsys):
        with patch("cli.score", return_value=_make_report(score=50)):
            code = _run_cli("--psbt", "cHNidP8BA", "--fail-below", "60")
        assert code == 1

    def test_exits_0_with_no_threshold(self, capsys):
        with patch("cli.score", return_value=_make_report(score=10)):
            code = _run_cli("--psbt", "cHNidP8BA")
        assert code == 0


class TestParseError:
    def test_exits_2_on_value_error(self, capsys):
        with patch("cli.score", side_effect=ValueError("Invalid PSBT base64")):
            code = _run_cli("--psbt", "bad_input")
        assert code == 2

    def test_json_error_on_parse_failure(self, capsys):
        with patch("cli.score", side_effect=ValueError("Invalid PSBT base64")):
            code = _run_cli("--psbt", "bad_input", "--json")
        assert code == 2
        out = json.loads(capsys.readouterr().out)
        assert "error" in out
        assert "Invalid PSBT base64" in out["error"]


class TestJsonOutput:
    def test_json_contains_score_and_findings(self, capsys):
        with patch("cli.score", return_value=_make_report(score=72)):
            code = _run_cli("--psbt", "cHNidP8BA", "--json")
        assert code == 0
        out = json.loads(capsys.readouterr().out)
        assert out["score"] == 72
        assert "findings" in out
        assert "checks" in out

    def test_json_and_fail_below_composable(self, capsys):
        with patch("cli.score", return_value=_make_report(score=45)):
            code = _run_cli("--psbt", "cHNidP8BA", "--fail-below", "60", "--json")
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["score"] == 45
