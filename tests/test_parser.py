"""Tests for PSBT/rawtx/txid parser."""
import base64


P2WPKH_SCRIPT = "0014" + "11" * 20
P2TR_SCRIPT = "5120" + "22" * 32


def _compact_size(n: int) -> bytes:
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + n.to_bytes(2, "little")
    if n <= 0xFFFFFFFF:
        return b"\xfe" + n.to_bytes(4, "little")
    return b"\xff" + n.to_bytes(8, "little")


def _varbytes(raw: bytes) -> bytes:
    return _compact_size(len(raw)) + raw


def _txout(value: int, script_hex: str) -> bytes:
    return value.to_bytes(8, "little", signed=True) + _varbytes(bytes.fromhex(script_hex))


def _sample_rawtx_hex() -> str:
    return (
        "02000000"
        "01"
        + ("00" * 31 + "01")
        + "00000000"
        + "00"
        + "ffffffff"
        + "02"
        + _txout(1001, P2WPKH_SCRIPT).hex()
        + _txout(2002, P2TR_SCRIPT).hex()
        + "00000000"
    )


def _sample_prevtx_hex() -> str:
    return (
        "02000000"
        "01"
        + ("00" * 32)
        + "ffffffff"
        + "00"
        + "ffffffff"
        + "01"
        + _txout(7777, P2WPKH_SCRIPT).hex()
        + "00000000"
    )


def _sample_psbt_b64() -> str:
    rawtx = bytes.fromhex(_sample_rawtx_hex())
    witness_utxo = _txout(5000, P2WPKH_SCRIPT)
    psbt = (
        b"psbt\xff"
        + _varbytes(b"\x00") + _varbytes(rawtx)
        + b"\x00"
        + _varbytes(b"\x01") + _varbytes(witness_utxo)
        + b"\x00"
        + b"\x00"
        + b"\x00"
    )
    return base64.b64encode(psbt).decode()


def test_rawtx_parses_inputs_and_outputs(monkeypatch):
    import scorer.parser as parser

    monkeypatch.setattr(
        parser,
        "get_tx_hex",
        lambda txid: (_ for _ in ()).throw(RuntimeError("lookup unavailable")),
    )

    tx, meta = parser.parse(_sample_rawtx_hex())

    assert meta == {"version": 0}
    assert tx.version == 2
    assert len(tx.inputs) == 1
    assert len(tx.outputs) == 2
    assert tx.inputs[0].txid == "01" + "00" * 31
    assert tx.outputs[0].value == 1001
    assert tx.outputs[0].script_pubkey.hex() == P2WPKH_SCRIPT


def test_rawtx_enriches_input_prevout(monkeypatch):
    import scorer.parser as parser

    monkeypatch.setattr(parser, "get_tx_hex", lambda txid: _sample_prevtx_hex())

    tx, _ = parser.parse(_sample_rawtx_hex())

    assert tx.inputs[0].value == 7777
    assert tx.inputs[0].script_pubkey.hex() == P2WPKH_SCRIPT


def test_psbt_input_detected_and_prevout_applied():
    from scorer.parser import parse

    tx, meta = parse(_sample_psbt_b64())

    assert meta == {"version": 0}
    assert len(tx.inputs) == 1
    assert tx.inputs[0].value == 5000
    assert tx.inputs[0].script_pubkey.hex() == P2WPKH_SCRIPT
    assert tx.inputs[0].address
    assert tx.inputs[0].address.startswith("bc1q")


def test_txid_dispatches_to_lookup(monkeypatch):
    import scorer.parser as parser

    txid = "a" * 64
    monkeypatch.setattr(parser, "get_tx", lambda value: {"hex": _sample_rawtx_hex()})
    monkeypatch.setattr(parser, "get_tx_hex", lambda value: _sample_prevtx_hex())

    tx, _ = parser.parse(txid)

    assert len(tx.inputs) == 1
    assert len(tx.outputs) == 2


def test_txid_fetch_failure_returns_clear_error(monkeypatch):
    import pytest
    import scorer.parser as parser

    monkeypatch.setattr(parser, "get_tx", lambda value: (_ for _ in ()).throw(RuntimeError("timeout")))

    with pytest.raises(ValueError, match="Could not fetch txid"):
        parser.parse("c" * 64)


def test_parse_as_rejects_invalid_txid():
    import pytest
    from scorer.parser import parse_as

    with pytest.raises(ValueError, match="Invalid txid"):
        parse_as("not-a-txid", "txid")


def test_parse_as_rejects_invalid_rawtx():
    import pytest
    from scorer.parser import parse_as

    with pytest.raises(ValueError, match="Invalid raw transaction hex"):
        parse_as("xyz", "rawtx")


def test_txid_uses_mempool_prevout_metadata(monkeypatch):
    import scorer.parser as parser

    txid = "b" * 64
    monkeypatch.setattr(
        parser,
        "get_tx",
        lambda value: {
            "hex": _sample_rawtx_hex(),
            "vin": [
                {
                    "prevout": {
                        "value": 8888,
                        "scriptpubkey": P2TR_SCRIPT,
                        "scriptpubkey_address": "bc1ptest",
                    }
                }
            ],
        },
    )
    monkeypatch.setattr(parser, "get_tx_hex", lambda value: _sample_prevtx_hex())

    tx, _ = parser.parse(txid)

    assert tx.inputs[0].value == 8888
    assert tx.inputs[0].script_pubkey.hex() == P2TR_SCRIPT
    assert tx.inputs[0].address == "bc1ptest"
