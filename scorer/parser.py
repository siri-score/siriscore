"""Parse PSBT (BIP-174/370) or raw tx hex into a unified transaction object."""
import base64
from dataclasses import dataclass

from scorer.lookup import get_tx, get_tx_hex


@dataclass
class TxInput:
    txid: str
    vout: int
    script_sig: bytes
    sequence: int
    script_pubkey: bytes = b""
    value: int | None = None
    address: str | None = None


@dataclass
class TxOutput:
    value: int
    script_pubkey: bytes


@dataclass
class ParsedTx:
    version: int
    inputs: list[TxInput]
    outputs: list[TxOutput]
    locktime: int


def parse(input_str: str):
    """Accept base64 PSBT, raw hex, or txid. Returns (tx, psbt_meta)."""
    input_str = input_str.strip()

    if len(input_str) == 64 and all(c in "0123456789abcdefABCDEF" for c in input_str):
        return _parse_txid(input_str)

    if input_str.startswith("cHNidP"):
        return _parse_psbt(input_str)

    return _parse_rawtx(input_str)


def parse_as(input_str: str, input_type: str):
    """Parse input using the user's selected input type."""
    input_str = input_str.strip()
    normalized_type = input_type.strip().lower()

    if normalized_type == "txid":
        if not _is_txid(input_str):
            raise ValueError("Invalid txid: expected 64 hexadecimal characters")
        return _parse_txid(input_str)

    if normalized_type == "psbt":
        if not input_str:
            raise ValueError("Invalid PSBT: input is empty")
        return _parse_psbt(input_str)

    if normalized_type == "rawtx":
        if not _is_hex(input_str):
            raise ValueError("Invalid raw transaction hex")
        return _parse_rawtx(input_str)

    raise ValueError("Invalid input type: expected psbt, rawtx, or txid")


def _is_txid(value: str) -> bool:
    return len(value) == 64 and _is_hex(value)


def _is_hex(value: str) -> bool:
    return bool(value) and len(value) % 2 == 0 and all(c in "0123456789abcdefABCDEF" for c in value)


def _parse_psbt(b64: str):
    try:
        data = base64.b64decode(b64, validate=True)
    except ValueError as exc:
        raise ValueError("Invalid PSBT base64") from exc

    reader = _Reader(data)
    if reader.read(5) != b"psbt\xff":
        raise ValueError("Invalid PSBT magic bytes")

    globals_map = _read_psbt_map(reader)
    unsigned_tx = None
    psbt_version = 0

    for key, value in globals_map:
        key_type = key[0]
        if key_type == 0x00 and len(key) == 1:
            unsigned_tx = value
        elif key_type == 0xFB and len(value) == 4:
            psbt_version = int.from_bytes(value, "little")

    if unsigned_tx is None:
        raise NotImplementedError("PSBT v2 without an unsigned tx is not supported yet")

    tx, _ = _parse_rawtx(unsigned_tx.hex(), enrich_prevouts=False)

    for txin in tx.inputs:
        input_map = _read_psbt_map(reader)
        _apply_psbt_input_utxo(txin, input_map)

    for _ in tx.outputs:
        _read_psbt_map(reader)

    return tx, {"version": psbt_version}


def _parse_rawtx(hex_str: str, enrich_prevouts: bool = True):
    try:
        data = bytes.fromhex(hex_str.strip())
    except ValueError as exc:
        raise ValueError("Invalid raw transaction hex") from exc

    reader = _Reader(data)
    version = reader.read_uint32()

    marker_or_count = reader.read_uint8()
    has_witness = marker_or_count == 0
    if has_witness:
        flag = reader.read_uint8()
        if flag == 0:
            raise ValueError("Invalid segwit transaction marker/flag")
        input_count = reader.read_compact_size()
    else:
        reader.rewind(1)
        input_count = reader.read_compact_size()

    inputs = []
    for _ in range(input_count):
        txid = reader.read(32)[::-1].hex()
        vout = reader.read_uint32()
        script_sig = reader.read_varbytes()
        sequence = reader.read_uint32()
        inputs.append(TxInput(txid=txid, vout=vout, script_sig=script_sig, sequence=sequence))

    outputs = [_read_txout(reader) for _ in range(reader.read_compact_size())]

    if has_witness:
        for _ in inputs:
            for _ in range(reader.read_compact_size()):
                reader.read_varbytes()

    locktime = reader.read_uint32()
    if not reader.is_done:
        raise ValueError("Raw transaction has unexpected trailing bytes")

    tx = ParsedTx(version=version, inputs=inputs, outputs=outputs, locktime=locktime)
    if enrich_prevouts:
        _enrich_prevouts(tx)

    return tx, {"version": 0}


def _parse_txid(txid: str):
    try:
        raw = get_tx(txid)
        tx_hex = raw.get("hex") or get_tx_hex(txid)
    except Exception as exc:
        raise ValueError(
            "Could not fetch txid from mempool.space or blockstream.info. "
            "Check your network connection and try again."
        ) from exc
    tx, meta = _parse_rawtx(tx_hex, enrich_prevouts=False)
    _apply_mempool_prevouts(tx, raw)
    _enrich_prevouts(tx)
    return tx, meta


def _apply_psbt_input_utxo(txin: TxInput, input_map: list[tuple[bytes, bytes]]) -> None:
    for key, value in input_map:
        if not key:
            continue
        key_type = key[0]
        if key_type == 0x01:
            txout = _read_txout(_Reader(value))
            txin.value = txout.value
            txin.script_pubkey = txout.script_pubkey
            return
        if key_type == 0x00:
            prev_tx, _ = _parse_rawtx(value.hex(), enrich_prevouts=False)
            if txin.vout < len(prev_tx.outputs):
                prevout = prev_tx.outputs[txin.vout]
                txin.value = prevout.value
                txin.script_pubkey = prevout.script_pubkey


def _enrich_prevouts(tx: ParsedTx) -> None:
    for txin in tx.inputs:
        if txin.script_pubkey and txin.value is not None:
            continue
        if txin.txid == "0" * 64 or txin.vout == 0xFFFFFFFF:
            continue

        try:
            prev_tx, _ = _parse_rawtx(get_tx_hex(txin.txid), enrich_prevouts=False)
        except Exception:
            continue

        if txin.vout >= len(prev_tx.outputs):
            continue

        prevout = prev_tx.outputs[txin.vout]
        txin.value = prevout.value
        txin.script_pubkey = prevout.script_pubkey


def _apply_mempool_prevouts(tx: ParsedTx, tx_json: dict) -> None:
    vins = tx_json.get("vin", [])
    for txin, vin in zip(tx.inputs, vins):
        prevout = vin.get("prevout") or {}
        if "value" in prevout:
            txin.value = prevout["value"]
        if "scriptpubkey" in prevout:
            try:
                txin.script_pubkey = bytes.fromhex(prevout["scriptpubkey"])
            except ValueError:
                pass
        if "scriptpubkey_address" in prevout:
            txin.address = prevout["scriptpubkey_address"]


def _read_txout(reader: "_Reader") -> TxOutput:
    return TxOutput(value=reader.read_int64(), script_pubkey=reader.read_varbytes())


def _read_psbt_map(reader: "_Reader") -> list[tuple[bytes, bytes]]:
    entries = []
    while True:
        key_len = reader.read_compact_size()
        if key_len == 0:
            return entries
        key = reader.read(key_len)
        value = reader.read_varbytes()
        entries.append((key, value))


class _Reader:
    def __init__(self, data: bytes):
        self._data = data
        self._offset = 0

    @property
    def is_done(self) -> bool:
        return self._offset == len(self._data)

    def rewind(self, n: int) -> None:
        self._offset = max(0, self._offset - n)

    def read(self, n: int) -> bytes:
        end = self._offset + n
        if end > len(self._data):
            raise ValueError("Unexpected end of transaction data")
        chunk = self._data[self._offset:end]
        self._offset = end
        return chunk

    def read_uint8(self) -> int:
        return self.read(1)[0]

    def read_uint16(self) -> int:
        return int.from_bytes(self.read(2), "little")

    def read_uint32(self) -> int:
        return int.from_bytes(self.read(4), "little")

    def read_int64(self) -> int:
        return int.from_bytes(self.read(8), "little", signed=True)

    def read_compact_size(self) -> int:
        first = self.read_uint8()
        if first < 0xFD:
            return first
        if first == 0xFD:
            return self.read_uint16()
        if first == 0xFE:
            return self.read_uint32()
        return int.from_bytes(self.read(8), "little")

    def read_varbytes(self) -> bytes:
        return self.read(self.read_compact_size())
