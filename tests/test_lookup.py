"""Tests for explorer lookup fallback behavior."""
import requests


class _Response:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def test_get_tx_falls_back_to_blockstream(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if "mempool.space" in url:
            raise requests.Timeout("mempool slow")
        return _Response(payload={"txid": "btc", "status": {"block_height": 123}})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    tx = lookup.get_tx("btc")

    assert tx["status"]["block_height"] == 123
    assert calls == [
        "https://mempool.space/api/tx/btc",
        "https://blockstream.info/api/tx/btc",
    ]


def test_get_tx_hex_falls_back_to_blockstream(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if "mempool.space" in url:
            raise requests.Timeout("mempool timedout")
        if url.endswith("/hex"):
            return _Response(text="02000000")
        return _Response(payload={"txid": "btc"})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(lookup, "_hex_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    assert lookup.get_tx_hex("btc") == "02000000"
    assert calls == [
        "https://mempool.space/api/tx/btc",
        "https://blockstream.info/api/tx/btc",
        "https://mempool.space/api/tx/btc/hex",
        "https://blockstream.info/api/tx/btc/hex",
    ]


def test_get_tx_uses_mempool_first(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _Response(payload={"txid": "btc"})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    lookup.get_tx("btc")

    assert calls == ["https://mempool.space/api/tx/btc"]


def test_successful_mempool_response_does_not_call_blockstream(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _Response(payload={"txid": "btc"})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    lookup.get_tx("btc")

    assert len(calls) == 1
    assert calls[0].startswith("https://mempool.space")


def test_get_tx_hex_uses_mempool_before_blockstream(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if url.endswith("/hex"):
            return _Response(text="02000000")
        return _Response(payload={})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(lookup, "_hex_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    assert lookup.get_tx_hex("btc") == "02000000"
    assert calls == [
        "https://mempool.space/api/tx/btc",
        "https://mempool.space/api/tx/btc/hex",
    ]


def test_get_address_txs_uses_mempool_first(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _Response(payload=[])

    monkeypatch.setattr(lookup, "_address_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    assert lookup.get_address_txs("bc1qexample") == []
    assert calls == ["https://mempool.space/api/address/bc1qexample/txs"]
