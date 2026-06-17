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


def test_get_tx_falls_back_to_mempool(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if "blockstream.info" in url:
            raise requests.Timeout("blockstream slow")
        return _Response(payload={"txid": "abc", "status": {"block_height": 123}})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    tx = lookup.get_tx("abc")

    assert tx["status"]["block_height"] == 123
    assert calls == [
        "https://blockstream.info/api/tx/abc",
        "https://mempool.space/api/tx/abc",
    ]


def test_get_tx_hex_falls_back_to_mempool(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if "blockstream.info" in url:
            raise requests.Timeout("blockstream slow")
        if url.endswith("/hex"):
            return _Response(text="02000000")
        return _Response(payload={"txid": "abc"})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(lookup, "_hex_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    assert lookup.get_tx_hex("abc") == "02000000"
    assert calls == [
        "https://blockstream.info/api/tx/abc",
        "https://mempool.space/api/tx/abc",
        "https://blockstream.info/api/tx/abc/hex",
        "https://mempool.space/api/tx/abc/hex",
    ]


def test_get_tx_uses_blockstream_first(monkeypatch):
    import scorer.lookup as lookup

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        return _Response(payload={"txid": "abc"})

    monkeypatch.setattr(lookup, "_cache", {})
    monkeypatch.setattr(requests, "get", fake_get)

    lookup.get_tx("abc")

    assert calls == ["https://blockstream.info/api/tx/abc"]
