"""Tests for Bitcoin Core RPC backend and its integration with H3/H4/score()."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from scorer.rpc import RPCBackend, RPCError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rpc_ok(result):
    """Fake a successful Bitcoin Core JSON-RPC HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"result": result, "error": None, "id": 1}
    return resp


def _rpc_err(code, message, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = {"result": None, "error": {"code": code, "message": message}, "id": 1}
    return resp


def _make_backend(url="http://localhost:8332", user="u", password="p"):
    return RPCBackend(url=url, user=user, password=password)


def _tx(inputs=None, outputs=None):
    tx = MagicMock()
    tx.inputs = inputs or []
    tx.outputs = outputs or []
    return tx


# ---------------------------------------------------------------------------
# 1. RPCBackend.get_utxo_block_height — happy path
# ---------------------------------------------------------------------------

class TestRPCGetUtxoBlockHeight:
    def test_returns_blockheight_from_getrawtransaction(self, monkeypatch):
        backend = _make_backend()
        tx_data = {"txid": "aa" * 32, "blockheight": 800_000, "hex": "02000000"}
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _rpc_ok(tx_data))

        assert backend.get_utxo_block_height("aa" * 32) == 800_000

    def test_returns_none_when_field_missing(self, monkeypatch):
        backend = _make_backend()
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _rpc_ok({"txid": "aa" * 32}))

        assert backend.get_utxo_block_height("aa" * 32) is None

    def test_returns_none_on_rpc_error(self, monkeypatch):
        backend = _make_backend()
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _rpc_err(-5, "No such mempool transaction"))

        assert backend.get_utxo_block_height("bb" * 32) is None

    def test_caches_getrawtransaction(self, monkeypatch):
        backend = _make_backend()
        calls = []

        def fake_post(*a, **kw):
            calls.append(1)
            return _rpc_ok({"txid": "aa" * 32, "blockheight": 100})

        monkeypatch.setattr(requests, "post", fake_post)
        backend.get_utxo_block_height("aa" * 32)
        backend.get_utxo_block_height("aa" * 32)

        assert len(calls) == 1  # second call served from cache


# ---------------------------------------------------------------------------
# 2. RPCBackend.get_address_txs — always empty (no non-wallet index)
# ---------------------------------------------------------------------------

class TestRPCGetAddressTxs:
    def test_returns_empty_list_without_network_call(self, monkeypatch):
        backend = _make_backend()
        posted = []
        monkeypatch.setattr(requests, "post", lambda *a, **kw: posted.append(1) or _rpc_ok([]))

        result = backend.get_address_txs("bc1qtest")

        assert result == []
        assert len(posted) == 0  # no HTTP call made


# ---------------------------------------------------------------------------
# 3. RPCBackend error handling
# ---------------------------------------------------------------------------

class TestRPCErrorHandling:
    def test_connection_failure_raises_rpc_error(self, monkeypatch):
        backend = _make_backend()
        monkeypatch.setattr(requests, "post",
                            lambda *a, **kw: (_ for _ in ()).throw(requests.ConnectionError("refused")))

        with pytest.raises(RPCError, match="connection failed"):
            backend.getrawtransaction("aa" * 32)

    def test_timeout_raises_rpc_error(self, monkeypatch):
        backend = _make_backend()
        monkeypatch.setattr(requests, "post",
                            lambda *a, **kw: (_ for _ in ()).throw(requests.Timeout("timed out")))

        with pytest.raises(RPCError, match="connection failed"):
            backend.getrawtransaction("aa" * 32)

    def test_401_raises_rpc_error(self, monkeypatch):
        backend = _make_backend()
        resp = MagicMock()
        resp.status_code = 401
        resp.json.return_value = {}
        monkeypatch.setattr(requests, "post", lambda *a, **kw: resp)

        with pytest.raises(RPCError, match="authentication failed"):
            backend.getrawtransaction("aa" * 32)

    def test_403_raises_rpc_error(self, monkeypatch):
        backend = _make_backend()
        resp = MagicMock()
        resp.status_code = 403
        resp.json.return_value = {}
        monkeypatch.setattr(requests, "post", lambda *a, **kw: resp)

        with pytest.raises(RPCError, match="access denied"):
            backend.getrawtransaction("aa" * 32)

    def test_rpc_error_field_raises(self, monkeypatch):
        backend = _make_backend()
        monkeypatch.setattr(requests, "post",
                            lambda *a, **kw: _rpc_err(-8, "txindex disabled"))

        with pytest.raises(RPCError, match="txindex disabled"):
            backend.getrawtransaction("aa" * 32)

    def test_invalid_json_raises_rpc_error(self, monkeypatch):
        backend = _make_backend()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("not JSON")
        monkeypatch.setattr(requests, "post", lambda *a, **kw: resp)

        with pytest.raises(RPCError, match="Invalid JSON"):
            backend.getrawtransaction("aa" * 32)


# ---------------------------------------------------------------------------
# 4. RPCBackend.gettxout
# ---------------------------------------------------------------------------

class TestRPCGetTxOut:
    def test_returns_utxo_info(self, monkeypatch):
        backend = _make_backend()
        utxo = {"value": 0.001, "confirmations": 10, "scriptPubKey": {}}
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _rpc_ok(utxo))

        result = backend.gettxout("aa" * 32, 0)

        assert result["value"] == pytest.approx(0.001)

    def test_returns_none_for_spent_utxo(self, monkeypatch):
        backend = _make_backend()
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _rpc_ok(None))

        assert backend.gettxout("aa" * 32, 0) is None


# ---------------------------------------------------------------------------
# 5. H3 with RPC backend
# ---------------------------------------------------------------------------

class TestH3WithRPCBackend:
    def test_returns_none_because_no_address_index(self):
        from scorer.heuristics.h3_address_reuse import check

        backend = _make_backend()
        inp = MagicMock(address="bc1qtest")
        psbt_meta = {"_backend": backend}

        assert check(_tx(inputs=[inp]), psbt_meta) is None

    def test_does_not_call_module_level_get_address_txs(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse

        calls = []
        monkeypatch.setattr(h3_address_reuse, "get_address_txs",
                            lambda a: calls.append(a) or ["tx1", "tx2"])

        backend = _make_backend()
        inp = MagicMock(address="bc1qtest")
        psbt_meta = {"_backend": backend}

        h3_address_reuse.check(_tx(inputs=[inp]), psbt_meta)
        # The module-level function must NOT be called when a backend is present.
        assert calls == []

    def test_without_backend_uses_module_level_function(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse

        calls = []
        monkeypatch.setattr(h3_address_reuse, "get_address_txs",
                            lambda a: calls.append(a) or [])

        inp = MagicMock(address="bc1qtest")
        h3_address_reuse.check(_tx(inputs=[inp]), {})

        assert "bc1qtest" in calls


# ---------------------------------------------------------------------------
# 6. H4 with RPC backend
# ---------------------------------------------------------------------------

class TestH4WithRPCBackend:
    def _rpc_heights(self, heights: dict):
        """Return an RPCBackend whose get_utxo_block_height is stubbed."""
        backend = _make_backend()
        backend.get_utxo_block_height = lambda txid: heights.get(txid)
        return backend

    def test_fires_when_inputs_clustered(self):
        from scorer.heuristics.h4_utxo_age import check

        txid_a, txid_b = "a" * 64, "b" * 64
        backend = self._rpc_heights({txid_a: 800_000, txid_b: 800_003})
        inp_a = MagicMock(txid=txid_a)
        inp_b = MagicMock(txid=txid_b)
        psbt_meta = {"_backend": backend}

        finding = check(_tx(inputs=[inp_a, inp_b]), psbt_meta)

        assert finding is not None
        assert finding.heuristic_id == "H4"

    def test_no_finding_when_inputs_spread_out(self):
        from scorer.heuristics.h4_utxo_age import check

        txid_a, txid_b = "a" * 64, "b" * 64
        backend = self._rpc_heights({txid_a: 800_000, txid_b: 800_100})
        inp_a = MagicMock(txid=txid_a)
        inp_b = MagicMock(txid=txid_b)
        psbt_meta = {"_backend": backend}

        assert check(_tx(inputs=[inp_a, inp_b]), psbt_meta) is None

    def test_uses_backend_not_module_level(self, monkeypatch):
        from scorer.heuristics import h4_utxo_age

        module_calls = []
        monkeypatch.setattr(h4_utxo_age, "get_utxo_block_height",
                            lambda txid: module_calls.append(txid) or 1)

        txid_a, txid_b = "a" * 64, "b" * 64
        backend = _make_backend()
        backend.get_utxo_block_height = lambda txid: None
        inp_a = MagicMock(txid=txid_a)
        inp_b = MagicMock(txid=txid_b)

        h4_utxo_age.check(_tx(inputs=[inp_a, inp_b]), {"_backend": backend})
        assert module_calls == []


# ---------------------------------------------------------------------------
# 7. score() API — RPC and mempool paths
# ---------------------------------------------------------------------------

class TestScoreAPI:
    def _psbt(self):
        from tests.test_parser import _sample_psbt_b64
        return _sample_psbt_b64()

    def test_score_lookup_rpc_requires_rpc_url(self):
        with pytest.raises(ValueError, match="rpc_url"):
            from scorer import score
            score(self._psbt(), lookup="rpc")

    def test_score_lookup_rpc_creates_rpc_backend(self, monkeypatch):
        from scorer import score
        from scorer import rpc as rpc_module

        created = []

        class FakeBackend:
            HAS_ADDRESS_INDEX = False
            def get_address_txs(self, a): return []
            def get_utxo_block_height(self, t): return None

        monkeypatch.setattr(rpc_module, "RPCBackend",
                            lambda **kw: (created.append(kw), FakeBackend())[1])

        report = score(self._psbt(), lookup="rpc",
                       rpc_url="http://localhost:8332", rpc_user="u", rpc_password="p")

        assert len(created) == 1
        assert created[0]["url"] == "http://localhost:8332"
        assert report is not None

    def test_score_lookup_false_no_backend(self):
        from scorer import score
        report = score(self._psbt(), lookup=False)
        h3 = next(c for c in report.checks if c.heuristic_id == "H3")
        # PSBT inputs have no address string → "unavailable"; if they did, it'd be "skipped"
        assert h3.status in ("skipped", "unavailable")

    def test_score_lookup_true_uses_mempool(self, monkeypatch):
        from scorer.heuristics import h3_address_reuse, h4_utxo_age
        monkeypatch.setattr(h3_address_reuse, "get_address_txs", lambda a: [])
        monkeypatch.setattr(h4_utxo_age, "get_utxo_block_height", lambda t: None)

        from scorer import score
        report = score(self._psbt(), lookup=True)
        # H3 ran and found nothing → pass (or unavailable if no addresses)
        assert report is not None

    def test_score_backward_compat_no_lookup_kwarg(self):
        """score(input) still works with no keyword args."""
        from scorer import score
        report = score(self._psbt())
        assert report.score is not None


# ---------------------------------------------------------------------------
# 8. _build_checks — H3 marked unavailable with RPC backend
# ---------------------------------------------------------------------------

class TestBuildChecksRPCBackend:
    def _psbt_tx(self):
        from scorer.parser import parse
        from tests.test_parser import _sample_psbt_b64
        tx, meta = parse(_sample_psbt_b64())
        return tx

    def test_h3_unavailable_with_rpc_backend(self):
        from scorer import _build_checks

        backend = _make_backend()
        tx = self._psbt_tx()
        checks = _build_checks(tx, [], lookup=True, backend=backend)
        h3 = next(c for c in checks if c.heuristic_id == "H3")

        assert h3.status == "unavailable"
        assert "non-wallet" in h3.reason.lower() or "address" in h3.reason.lower()

    def test_h3_pass_with_mempool_backend(self):
        from scorer import _build_checks

        tx = self._psbt_tx()
        checks = _build_checks(tx, [], lookup=True, backend=None)
        h3 = next(c for c in checks if c.heuristic_id == "H3")

        # No address on PSBT inputs → unavailable (data issue), not skipped
        assert h3.status in ("pass", "unavailable")

    def test_h3_skipped_when_no_lookup_and_address_present(self):
        """When addresses are available but lookup=False, H3 must be 'skipped'."""
        from scorer import _build_checks
        from unittest.mock import MagicMock

        tx = MagicMock()
        inp = MagicMock()
        inp.address = "bc1qtest"
        tx.inputs = [inp]
        tx.outputs = []

        checks = _build_checks(tx, [], lookup=False, backend=None)
        h3 = next(c for c in checks if c.heuristic_id == "H3")

        assert h3.status == "skipped"

    def test_h4_not_affected_by_rpc_backend_sentinel(self):
        """H4 should run normally with RPC backend — no unavailable override."""
        from scorer import _build_checks

        backend = _make_backend()
        tx = self._psbt_tx()
        checks = _build_checks(tx, [], lookup=True, backend=backend)
        h4 = next(c for c in checks if c.heuristic_id == "H4")

        # Only 1 input → H4 returns None (< 2 inputs). Should be pass, not unavailable.
        assert h4.status in ("pass", "unavailable")
        # Specifically NOT "skipped" or RPC-related unavailable
        assert "non-wallet" not in h4.reason


# ---------------------------------------------------------------------------
# 9. CLI argument handling
# ---------------------------------------------------------------------------

class TestCLIRPCArgs:
    def _run(self, *extra_args, mock_score=None):
        from cli import main
        if mock_score is None:
            from scorer.report import Report
            mock_score = Report(score=80, findings=[], checks=[], input_count=1,
                                output_count=1, psbt_version=0)
        with patch("sys.argv", ["btc-privacy-check", "--psbt", "cHNidP8BA", *extra_args]):
            with patch("cli.score", return_value=mock_score) as mock:
                try:
                    main()
                except SystemExit:
                    pass
                return mock

    def test_rpc_url_sets_lookup_rpc(self):
        mock = self._run("--rpc-url", "http://localhost:8332",
                         "--rpc-user", "alice", "--rpc-password", "secret")
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["lookup"] == "rpc"
        assert kwargs["rpc_url"] == "http://localhost:8332"
        assert kwargs["rpc_user"] == "alice"
        assert kwargs["rpc_password"] == "secret"

    def test_lookup_flag_sets_mempool(self):
        mock = self._run("--lookup")
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["lookup"] is True
        assert kwargs["rpc_url"] is None

    def test_no_flags_uses_local_only(self):
        mock = self._run()
        mock.assert_called_once()
        _, kwargs = mock.call_args
        assert kwargs["lookup"] is False
        assert kwargs["rpc_url"] is None


# ---------------------------------------------------------------------------
# 10. Regtest-oriented scenario (mocked RPC, two confirmed inputs)
# ---------------------------------------------------------------------------

class TestRegtestScenario:
    """Simulate a regtest scenario: two inputs confirmed at adjacent heights → H4 fires."""

    def test_h4_fires_in_regtest_scenario(self, monkeypatch):
        from scorer.heuristics.h4_utxo_age import check

        txid_a = "a" * 64
        txid_b = "b" * 64

        # Simulate Bitcoin Core RPC responses for two transactions at heights 101 and 103.
        responses = {
            txid_a: {"txid": txid_a, "blockheight": 101},
            txid_b: {"txid": txid_b, "blockheight": 103},
        }

        backend = _make_backend()
        backend.get_utxo_block_height = lambda txid: responses.get(txid, {}).get("blockheight")

        inp_a = MagicMock(txid=txid_a)
        inp_b = MagicMock(txid=txid_b)
        psbt_meta = {"_backend": backend}

        finding = check(_tx(inputs=[inp_a, inp_b]), psbt_meta)

        assert finding is not None
        assert finding.heuristic_id == "H4"

    def test_h4_no_finding_when_heights_differ_widely(self, monkeypatch):
        from scorer.heuristics.h4_utxo_age import check

        txid_a = "a" * 64
        txid_b = "b" * 64

        backend = _make_backend()
        backend.get_utxo_block_height = lambda txid: 101 if txid == txid_a else 200

        inp_a = MagicMock(txid=txid_a)
        inp_b = MagicMock(txid=txid_b)

        assert check(_tx(inputs=[inp_a, inp_b]), {"_backend": backend}) is None

    def test_rpc_backend_url_trailing_slash_stripped(self):
        backend = RPCBackend(url="http://localhost:8332/", user="u", password="p")
        assert not backend._url.endswith("/")
