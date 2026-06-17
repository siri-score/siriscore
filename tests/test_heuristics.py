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
