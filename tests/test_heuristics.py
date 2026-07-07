"""Unit tests for each heuristic module (one test per heuristic)."""
import pytest
from unittest.mock import MagicMock
from scorer.report import Severity


def _tx(inputs=None, outputs=None):
    tx = MagicMock()
    tx.inputs = inputs or []
    tx.outputs = outputs or []
    return tx


class TestH1ScriptMismatch:
    def test_fires_on_mismatch(self):
        from scorer.heuristics.h1_script_mismatch import check

        inp = MagicMock(script_pubkey=bytes.fromhex("0014" + "11" * 20))
        out = MagicMock(script_pubkey=bytes.fromhex("5120" + "22" * 32))

        finding = check(_tx(inputs=[inp], outputs=[out]), {})

        assert finding is not None
        assert finding.heuristic_id == "H1"
        assert finding.severity == Severity.CRITICAL

    def test_clean_on_uniform_types(self):
        from scorer.heuristics.h1_script_mismatch import check

        inp = MagicMock(script_pubkey=bytes.fromhex("0014" + "11" * 20))
        out = MagicMock(script_pubkey=bytes.fromhex("0014" + "22" * 20))

        assert check(_tx(inputs=[inp], outputs=[out]), {}) is None

    @pytest.mark.parametrize(
        ("script_hex", "expected"),
        [
            ("76a914" + "11" * 20 + "88ac", "p2pkh"),
            ("a914" + "11" * 20 + "87", "p2sh"),
            ("0014" + "11" * 20, "p2wpkh"),
            ("0020" + "11" * 32, "p2wsh"),
            ("5120" + "11" * 32, "p2tr"),
            ("6a", "unknown"),
        ],
    )
    def test_classifies_standard_scripts(self, script_hex, expected):
        from scorer.heuristics.h1_script_mismatch import classify_script

        assert classify_script(bytes.fromhex(script_hex)) == expected


class TestH2RoundAmount:
    def test_fires_on_round_output(self):
        from scorer.heuristics.h2_round_amount import check
        out = MagicMock()
        out.value = 1_000_000
        finding = check(_tx(outputs=[out]), {})
        assert finding is not None
        assert finding.heuristic_id == "H2"
        assert finding.severity == Severity.WARNING

    def test_clean_on_odd_amount(self):
        from scorer.heuristics.h2_round_amount import check
        out = MagicMock()
        out.value = 987_654
        assert check(_tx(outputs=[out]), {}) is None


class TestH5Consolidation:
    def test_fires_above_threshold(self):
        from scorer.heuristics.h5_consolidation import check
        inputs = [MagicMock() for _ in range(6)]
        finding = check(_tx(inputs=inputs), {})
        assert finding is not None
        assert finding.heuristic_id == "H5"

    def test_clean_below_threshold(self):
        from scorer.heuristics.h5_consolidation import check
        inputs = [MagicMock() for _ in range(3)]
        assert check(_tx(inputs=inputs), {}) is None


class TestH3AddressReuse:
    def test_caps_address_lookups(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse

        calls = []

        def fake_get_address_txs(address):
            calls.append(address)
            return []

        monkeypatch.setattr(h3_address_reuse, "get_address_txs", fake_get_address_txs)
        inputs = [MagicMock(address=f"bc1q{i}") for i in range(10)]

        assert h3_address_reuse.check(_tx(inputs=inputs), {}) is None
        assert len(calls) == h3_address_reuse.MAX_ADDRESS_LOOKUPS

    def test_generic_sp_suggestion_without_sp_output(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse

        monkeypatch.setattr(h3_address_reuse, "get_address_txs", lambda addr: ["tx1", "tx2"])
        monkeypatch.setattr(h3_address_reuse, "script_to_address", lambda spk: "bc1qregular")

        inp = MagicMock(address="bc1qreused")
        out = MagicMock(script_pubkey=b"\x00\x14" + b"\x11" * 20)

        finding = h3_address_reuse.check(_tx(inputs=[inp], outputs=[out]), {})

        assert finding is not None
        assert "Consider requesting a silent payment address" in finding.suggestion

    def test_sp_aware_suggestion_with_sp1q_output(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse

        monkeypatch.setattr(h3_address_reuse, "get_address_txs", lambda addr: ["tx1", "tx2"])
        monkeypatch.setattr(h3_address_reuse, "script_to_address", lambda spk: "sp1qrecipient")

        inp = MagicMock(address="bc1qreused")
        out = MagicMock(script_pubkey=b"\x51\x20" + b"\x22" * 32)

        finding = h3_address_reuse.check(_tx(inputs=[inp], outputs=[out]), {})

        assert finding is not None
        assert "Recipient supports silent payments" in finding.suggestion

    def test_sp_aware_suggestion_with_tsp1q_regtest_output(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse

        monkeypatch.setattr(h3_address_reuse, "get_address_txs", lambda addr: ["tx1", "tx2"])
        monkeypatch.setattr(h3_address_reuse, "script_to_address", lambda spk: "tsp1qrecipient")

        inp = MagicMock(address="bcrt1qreused")
        out = MagicMock(script_pubkey=b"\x51\x20" + b"\x22" * 32)

        finding = h3_address_reuse.check(_tx(inputs=[inp], outputs=[out]), {})

        assert finding is not None
        assert "Recipient supports silent payments" in finding.suggestion


class TestIsSilentPaymentAddress:
    def test_mainnet_sp_address(self):
        from scorer.utils import is_silent_payment_address
        assert is_silent_payment_address("sp1qrecipientaddress") is True

    def test_testnet_regtest_address(self):
        from scorer.utils import is_silent_payment_address
        assert is_silent_payment_address("tsp1qrecipientaddress") is True

    def test_non_sp_addresses(self):
        from scorer.utils import is_silent_payment_address
        assert is_silent_payment_address("bc1qaddress") is False
        assert is_silent_payment_address("bcrt1paddress") is False
        assert is_silent_payment_address("") is False


class TestH4UtxoAge:
    def test_skips_lookup_failures(self, monkeypatch):
        from scorer.heuristics import h4_utxo_age

        monkeypatch.setattr(
            h4_utxo_age,
            "get_utxo_block_height",
            lambda txid: (_ for _ in ()).throw(RuntimeError("lookup unavailable")),
        )

        inp = MagicMock(txid="a" * 64)

        assert h4_utxo_age.check(_tx(inputs=[inp]), {}) is None

    def test_caps_height_lookups(self, monkeypatch):
        from scorer.heuristics import h4_utxo_age

        calls = []

        def fake_get_utxo_block_height(txid):
            calls.append(txid)
            return None

        monkeypatch.setattr(h4_utxo_age, "get_utxo_block_height", fake_get_utxo_block_height)
        inputs = [MagicMock(txid=f"{i:064x}") for i in range(20)]

        assert h4_utxo_age.check(_tx(inputs=inputs), {}) is None
        assert len(calls) == h4_utxo_age.MAX_UTXO_HEIGHT_LOOKUPS


class TestH8TaintedLabel:
    def test_fires_on_exact_utxo_label(self, tmp_path, monkeypatch):
        import scorer.labels as labels_mod
        from scorer.heuristics.h8_tainted_label import check

        monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
        labels_mod.init_db()
        labels_mod.add_utxo_label("e" * 64, 1, "Specific labelled coin", "tainted")

        inp = MagicMock(txid="e" * 64, vout=1, address=None)
        finding = check(_tx(inputs=[inp]), {})

        assert finding is not None
        assert finding.heuristic_id == "H8"

    def test_fires_on_address_label(self, tmp_path, monkeypatch):
        import scorer.labels as labels_mod
        from scorer.heuristics.h8_tainted_label import check

        monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
        labels_mod.init_db()
        labels_mod.add_address_label("bc1qtainted", "Tainted receive address", "tainted")

        inp = MagicMock(txid="a" * 64, vout=0, address="bc1qtainted")
        finding = check(_tx(inputs=[inp]), {})

        assert finding is not None
        assert finding.heuristic_id == "H8"

    def test_fires_on_transaction_label(self, tmp_path, monkeypatch):
        import scorer.labels as labels_mod
        from scorer.heuristics.h8_tainted_label import check

        monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
        labels_mod.init_db()
        labels_mod.add_transaction_label("b" * 64, "Tainted transaction", "tainted")

        inp = MagicMock(txid="b" * 64, vout=0, address=None)
        finding = check(_tx(inputs=[inp]), {})

        assert finding is not None
        assert finding.heuristic_id == "H8"

    def test_fires_on_untagged_sparrow_label(self, tmp_path, monkeypatch):
        import scorer.labels as labels_mod
        from scorer.heuristics.h8_tainted_label import check

        monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
        labels_mod.init_db()
        labels_mod.add_address_label("bc1qlabelled", "Sparrow address label")

        inp = MagicMock(txid="c" * 64, vout=0, address="bc1qlabelled")
        finding = check(_tx(inputs=[inp]), {})

        assert finding is not None
        assert finding.heuristic_id == "H8"

    def test_clean_label_does_not_fire(self, tmp_path, monkeypatch):
        import scorer.labels as labels_mod
        from scorer.heuristics.h8_tainted_label import check

        monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
        labels_mod.init_db()
        labels_mod.add_address_label("bc1qclean", "Clean cold storage", "clean")

        inp = MagicMock(txid="d" * 64, vout=0, address="bc1qclean")

        assert check(_tx(inputs=[inp]), {}) is None


class TestH9CoinJoinInput:
    def test_fires_on_whirlpool_denom_input(self):
        from scorer.heuristics.h9_coinjoin_input import check

        inp = MagicMock(txid="a" * 64, vout=0, value=1_000_000, address=None)
        finding = check(_tx(inputs=[inp]), {})

        assert finding is not None
        assert finding.heuristic_id == "H9"
        assert finding.positive is True
        assert finding.weight == 0

    def test_fires_on_all_whirlpool_denominations(self):
        from scorer.heuristics.h9_coinjoin_input import check, WHIRLPOOL_DENOMS

        for denom in WHIRLPOOL_DENOMS:
            inp = MagicMock(txid="b" * 64, vout=0, value=denom, address=None)
            finding = check(_tx(inputs=[inp]), {})
            assert finding is not None, f"H9 should fire for denom {denom}"

    def test_fires_on_coinjoin_label(self, tmp_path, monkeypatch):
        import scorer.labels as labels_mod
        from scorer.heuristics.h9_coinjoin_input import check

        monkeypatch.setattr(labels_mod, "DB_PATH", tmp_path / "labels.db")
        labels_mod.init_db()
        labels_mod.add_label("e" * 64, 0, "Whirlpool 0.01 pool", "coinjoin")

        inp = MagicMock(txid="e" * 64, vout=0, value=999, address=None)
        finding = check(_tx(inputs=[inp]), {})

        assert finding is not None
        assert finding.heuristic_id == "H9"

    def test_does_not_fire_on_standard_input(self):
        from scorer.heuristics.h9_coinjoin_input import check

        inp = MagicMock(txid="f" * 64, vout=0, value=123_456, address=None)
        assert check(_tx(inputs=[inp]), {}) is None

    def test_does_not_fire_when_value_is_none(self):
        from scorer.heuristics.h9_coinjoin_input import check

        inp = MagicMock(txid="0" * 64, vout=0, value=None, address=None)
        assert check(_tx(inputs=[inp]), {}) is None


class TestH10CoinJoinTx:
    def _make_output(self, value):
        o = MagicMock()
        o.value = value
        return o

    def _make_input(self, script=b"\x00\x14" + b"\x11" * 20):
        i = MagicMock()
        i.script_pubkey = script
        return i

    def test_fires_on_whirlpool_structure(self):
        from scorer.heuristics.h10_coinjoin_tx import check

        inputs  = [self._make_input(bytes([i]) + b"\x14" + bytes(20)) for i in range(5)]
        outputs = [self._make_output(1_000_000)] * 5

        finding = check(_tx(inputs=inputs, outputs=outputs), {})

        assert finding is not None
        assert finding.heuristic_id == "H10"
        assert finding.positive is True
        assert finding.weight < 0

    def test_fires_on_wasabi_structure(self):
        from scorer.heuristics.h10_coinjoin_tx import check

        inputs  = [self._make_input(bytes([i]) + b"\x14" + bytes(20)) for i in range(6)]
        outputs = [self._make_output(500_000)] * 6

        finding = check(_tx(inputs=inputs, outputs=outputs), {})

        assert finding is not None
        assert finding.heuristic_id == "H10"

    def test_does_not_fire_on_standard_tx(self):
        from scorer.heuristics.h10_coinjoin_tx import check

        inputs  = [self._make_input(), self._make_input()]
        outputs = [self._make_output(800_000), self._make_output(200_000)]

        assert check(_tx(inputs=inputs, outputs=outputs), {}) is None

    def test_does_not_fire_on_two_equal_outputs_below_threshold(self):
        from scorer.heuristics.h10_coinjoin_tx import check

        # Only 2 equal outputs — below MIN_PARTICIPANTS=3
        inputs  = [self._make_input(), self._make_input()]
        outputs = [self._make_output(1_000_000), self._make_output(1_000_000)]

        assert check(_tx(inputs=inputs, outputs=outputs), {}) is None


class TestCoinJoinH5Suppression:
    def test_h9_suppresses_h5(self):
        import scorer
        from unittest.mock import patch

        with patch("scorer.heuristics.h9_coinjoin_input.check") as mock_h9, \
             patch("scorer.heuristics.h10_coinjoin_tx.check") as mock_h10, \
             patch("scorer.heuristics.h5_consolidation.check") as mock_h5:

            from scorer.report import Finding, Severity
            mock_h9.return_value = Finding("H9", Severity.INFO, "CJ input", "d", "s", 0, positive=True)
            mock_h10.return_value = None
            mock_h5.return_value = Finding("H5", Severity.WARNING, "High inputs", "d", "s", 10)

            from scorer.parser import ParsedTx, TxInput
            tx = ParsedTx(version=2, inputs=[TxInput("a"*64, 0, b"", 0xffffffff)], outputs=[], locktime=0)

            report = scorer._score_parsed(tx, {"version": 0})

            h5_ids = [f.heuristic_id for f in report.findings]
            assert "H5" not in h5_ids, "H5 should be suppressed when H9 fires"
            assert "H9" in h5_ids

    def test_h10_applies_score_bonus(self):
        import scorer
        from unittest.mock import patch

        with patch("scorer.heuristics.h10_coinjoin_tx.check") as mock_h10, \
             patch("scorer.heuristics.h9_coinjoin_input.check") as mock_h9:

            from scorer.report import Finding, Severity
            mock_h10.return_value = Finding("H10", Severity.INFO, "CJ tx", "d", "s", -10, positive=True)
            mock_h9.return_value = None

            from scorer.parser import ParsedTx, TxInput
            tx = ParsedTx(version=2, inputs=[TxInput("b"*64, 0, b"", 0xffffffff)], outputs=[], locktime=0)

            report = scorer._score_parsed(tx, {"version": 0})

            # Score should be 100 (all heuristics pass) + bonus capped at 100
            assert report.score == 100
            assert any(f.heuristic_id == "H10" for f in report.findings)


class TestH11PayjoinOpportunity:
    _BTCPAY_URI = (
        "bitcoin:BC1QYLH3U67J673H6Y6ALV70M0PL2YZ53TZHVXGG7U"
        "?amount=0.00001"
        "&pj=https://btcpay.example.com/api/v1/invoices/abc123/payjoin"
    )

    def test_fires_on_bip21_uri_with_pj_param(self):
        from scorer.heuristics.h11_payjoin_opportunity import check

        finding = check(_tx(), {"payment_uri": self._BTCPAY_URI})

        assert finding is not None
        assert finding.heuristic_id == "H11"
        assert finding.weight == 0
        assert finding.positive is True
        assert finding.severity.value == "info"

    def test_does_not_fire_without_uri(self):
        from scorer.heuristics.h11_payjoin_opportunity import check

        assert check(_tx(), {}) is None

    def test_does_not_fire_when_pj_absent_from_uri(self):
        from scorer.heuristics.h11_payjoin_opportunity import check

        uri = "bitcoin:BC1QYLH3U67J673H6Y6ALV70M0PL2YZ53TZHVXGG7U?amount=0.001"
        assert check(_tx(), {"payment_uri": uri}) is None

    def test_escalates_to_warning_when_h5_fires(self):
        from scorer.heuristics.h11_payjoin_opportunity import check

        inputs = [MagicMock() for _ in range(6)]
        finding = check(_tx(inputs=inputs), {"payment_uri": self._BTCPAY_URI})

        assert finding is not None
        assert finding.severity.value == "warning"
        assert "H5" in finding.title or "H5" in finding.detail

    def test_bip21_uri_key_alias(self):
        from scorer.heuristics.h11_payjoin_opportunity import check

        finding = check(_tx(), {"bip21_uri": self._BTCPAY_URI})
        assert finding is not None
        assert finding.heuristic_id == "H11"

    def test_extract_pj_endpoint(self):
        from scorer.heuristics.h11_payjoin_opportunity import _extract_pj_endpoint

        url = _extract_pj_endpoint(self._BTCPAY_URI)
        assert url == "https://btcpay.example.com/api/v1/invoices/abc123/payjoin"

    def test_extract_returns_none_for_plain_address(self):
        from scorer.heuristics.h11_payjoin_opportunity import _extract_pj_endpoint

        assert _extract_pj_endpoint("bitcoin:BC1QYLH3U67J673H6Y6ALV70M0PL2YZ53TZHVXGG7U") is None


class TestH13NLocktime:
    def test_fires_on_locktime_zero(self):
        from scorer.heuristics.h13_nlocktime import check

        tx = _tx()
        tx.locktime = 0
        finding = check(tx, {})

        assert finding is not None
        assert finding.heuristic_id == "H13"
        assert finding.severity == Severity.INFO
        assert finding.weight == 5

    def test_passes_on_plausible_block_height(self):
        from scorer.heuristics.h13_nlocktime import check

        tx = _tx()
        tx.locktime = 850_000
        assert check(tx, {}) is None

    def test_passes_on_locktime_one(self):
        from scorer.heuristics.h13_nlocktime import check

        tx = _tx()
        tx.locktime = 1
        assert check(tx, {}) is None

    def test_score_deduction_is_exactly_five(self):
        import scorer
        from unittest.mock import patch
        from scorer.report import Finding, Severity as Sev
        from scorer.parser import ParsedTx, TxInput

        with patch("scorer.heuristics.h13_nlocktime.check") as mock_h13:
            mock_h13.return_value = Finding("H13", Sev.INFO, "nLockTime", "d", "s", 5)

            # All other heuristics pass — use locktime=0 to trigger real H13, but
            # here we mock it directly and use a minimal tx with locktime=1 so nothing
            # else fires.
            tx = ParsedTx(version=2, inputs=[TxInput("a" * 64, 0, b"", 0xFFFFFFFF)], outputs=[], locktime=1)
            report = scorer._score_parsed(tx, {"version": 0})

        assert report.score == 95


class TestH14RBFSignalling:
    def test_all_inputs_signal_rbf(self):
        from scorer.heuristics.h14_rbf_signalling import check

        inputs = [MagicMock(sequence=0xFFFFFFFD), MagicMock(sequence=0)]
        finding = check(_tx(inputs=inputs), {})

        assert finding is not None
        assert finding.heuristic_id == "H14"
        assert finding.severity == Severity.INFO
        assert finding.weight == 0
        assert finding.positive is True

    def test_mixed_signalling_fires_warning(self):
        from scorer.heuristics.h14_rbf_signalling import check

        inputs = [MagicMock(sequence=0xFFFFFFFD), MagicMock(sequence=0xFFFFFFFF)]
        finding = check(_tx(inputs=inputs), {})

        assert finding is not None
        assert finding.heuristic_id == "H14"
        assert finding.severity == Severity.WARNING
        assert finding.weight == 5
        assert finding.positive is False

    def test_no_inputs_signal_rbf(self):
        from scorer.heuristics.h14_rbf_signalling import check

        inputs = [MagicMock(sequence=0xFFFFFFFF), MagicMock(sequence=0xFFFFFFFE)]
        finding = check(_tx(inputs=inputs), {})

        assert finding is not None
        assert finding.heuristic_id == "H14"
        assert finding.severity == Severity.INFO
        assert finding.weight == 0
        assert finding.positive is True

    def test_no_inputs_returns_none(self):
        from scorer.heuristics.h14_rbf_signalling import check

        assert check(_tx(inputs=[]), {}) is None

    def test_score_deduction_is_exactly_five_on_mixed_signalling(self):
        import scorer
        from scorer.parser import ParsedTx, TxInput

        tx = ParsedTx(
            version=2,
            inputs=[
                TxInput("a" * 64, 0, b"", 0xFFFFFFFD),
                TxInput("b" * 64, 1, b"", 0xFFFFFFFF),
            ],
            outputs=[],
            locktime=850_000,
        )
        report = scorer._score_parsed(tx, {"version": 0})

        assert report.score == 95
