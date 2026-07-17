"""Generate golden parity vectors for the Rust SDK (siriscore-sdk M1).

Runs fixture transactions through THIS Python engine and emits expected
score/findings/checks as JSON. The SDK replays every vector in
core/tests/golden_vectors.rs.

Usage:
    python3 tools/gen_golden_vectors.py > ../siriscore-sdk/core/tests/golden/vectors.json
"""
import base64
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Hermetic label store: fresh temp DB, swapped per fixture below.
os.environ["LABEL_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "labels.db")

from scorer import labels as labels_module, parser as parser_module, _score_parsed
from scorer.labels import add_address_label, add_transaction_label, add_utxo_label, init_db
from scorer.parser import parse_as, script_to_address


def varint(n: int) -> bytes:
    if n < 0xFD:
        return bytes([n])
    if n <= 0xFFFF:
        return b"\xfd" + struct.pack("<H", n)
    return b"\xfe" + struct.pack("<I", n)


def p2pkh(fill: int) -> bytes:
    return bytes([0x76, 0xA9, 0x14]) + bytes([fill] * 20) + bytes([0x88, 0xAC])


def p2wpkh(fill: int) -> bytes:
    return bytes([0x00, 0x14]) + bytes([fill] * 20)


def raw_tx(inputs, outputs, locktime=850_000, version=2) -> bytes:
    """inputs: [(txid_hex, vout)], outputs: [(value, spk)]"""
    tx = struct.pack("<i", version) + varint(len(inputs))
    for txid, vout in inputs:
        tx += bytes.fromhex(txid)[::-1] + struct.pack("<I", vout)
        tx += b"\x00" + struct.pack("<I", 0xFFFFFFFF)
    tx += varint(len(outputs))
    for value, spk in outputs:
        tx += struct.pack("<q", value) + varint(len(spk)) + spk
    tx += struct.pack("<I", locktime)
    return tx


def psbt(inputs, outputs, locktime=850_000) -> str:
    """inputs: [(txid_hex, vout, utxo_value, utxo_spk)]; witness_utxo per input."""
    tx = raw_tx([(t, v) for t, v, _, _ in inputs], outputs, locktime)
    out = b"psbt\xff" + varint(1) + b"\x00" + varint(len(tx)) + tx + b"\x00"
    for _, _, value, spk in inputs:
        if value is None:
            out += b"\x00"  # empty input map
        else:
            utxo = struct.pack("<q", value) + varint(len(spk)) + spk
            out += varint(1) + b"\x01" + varint(len(utxo)) + utxo + b"\x00"
    out += b"\x00" * len(outputs)  # empty output maps
    return base64.b64encode(out).decode()


TXID_A = "11" * 32
TXID_B = "22" * 32
TXID_C = "33" * 32

# A value that triggers nothing: non-round, non-dust, non-denomination.
PLAIN = 123_457
IN_SPK = p2wpkh(0xAA)
OUT_SPK = p2wpkh(0xBB)
PJ_URI = "bitcoin:bc1qexample?amount=0.01&pj=https://payjoin.example.org/pj"


def plain_inputs(n, value=1_234_567):
    return [("{:02x}".format(0x40 + i) * 32, 0, value, p2wpkh(0xA0 + i)) for i in range(n)]


def sorted_outputs(*values):
    return [(v, OUT_SPK) for v in sorted(values)]


# (name, kind, payload) — kind: "psbt" | "rawtx"; payload built lazily so each
# fixture is readable at a glance.
FIXTURES = [
    # H2
    ("h2_round_output_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 1_000_000))),
    ("h2_non_round_passes", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 234_569))),
    ("h2_zero_sat_output_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(0, PLAIN))),
    # H5
    ("h5_four_inputs_pass", "psbt",
     lambda: psbt(plain_inputs(4), sorted_outputs(PLAIN))),
    ("h5_five_inputs_fire", "psbt",
     lambda: psbt(plain_inputs(5), sorted_outputs(PLAIN))),
    # H6
    ("h6_dust_546_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 546, IN_SPK)], sorted_outputs(PLAIN))),
    ("h6_dust_547_passes", "psbt",
     lambda: psbt([(TXID_A, 0, 547, IN_SPK)], sorted_outputs(PLAIN))),
    ("h6_no_values_rawtx_unavailable", "rawtx",
     lambda: raw_tx([(TXID_A, 0)], sorted_outputs(PLAIN)).hex()),
    # H7
    ("h7_unsorted_inputs_fire", "psbt",
     lambda: psbt([(TXID_B, 0, 2_345_678, IN_SPK), (TXID_A, 0, 2_345_679, IN_SPK)],
                  sorted_outputs(PLAIN))),
    ("h7_unsorted_outputs_fire", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], [(PLAIN + 1, OUT_SPK), (PLAIN, OUT_SPK)])),
    ("h7_sorted_passes", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK), (TXID_B, 0, 2_345_679, IN_SPK)],
                  sorted_outputs(PLAIN, PLAIN + 1))),
    ("h7_single_input_output_passes", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN))),
    # H13
    ("h13_locktime_zero_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN), locktime=0)),
    ("h13_locktime_set_passes", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN), locktime=850_000)),
    # H10
    ("h10_whirlpool_fires", "psbt",
     lambda: psbt(plain_inputs(3), [(1_000_000, p2wpkh(0xB0 + i)) for i in range(3)])),
    ("h10_whirlpool_near_miss_two_inputs", "psbt",
     lambda: psbt(plain_inputs(2), [(1_000_000, p2wpkh(0xB0 + i)) for i in range(3)])),
    ("h10_wasabi_fires", "psbt",
     lambda: psbt(plain_inputs(6), [(50_001, p2wpkh(0xB0 + i)) for i in range(5)] + [(60_007, OUT_SPK)])),
    ("h10_wasabi_near_miss_four_inputs", "psbt",
     lambda: psbt(plain_inputs(4), [(50_001, p2wpkh(0xB0 + i)) for i in range(5)])),
    ("h10_joinmarket_fires", "psbt",
     lambda: psbt(plain_inputs(3), sorted_outputs(111_111, 222_223, 333_337))),
    ("h10_joinmarket_near_miss_same_scripts", "psbt",
     lambda: psbt([("{:02x}".format(0x40 + i) * 32, 0, 1_234_567, IN_SPK) for i in range(3)],
                  sorted_outputs(111_111, 222_223, 333_337))),
    ("h10_bonus_cannot_exceed_100", "psbt",
     lambda: psbt(plain_inputs(5), [(50_001, p2wpkh(0xB0 + i)) for i in range(5)])),
    # H9
    ("h9_whirlpool_denom_input_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 1_000_000, IN_SPK)], sorted_outputs(PLAIN, 234_569))),
    ("h9_fires_and_suppresses_h5", "psbt",
     lambda: psbt([(TXID_A, 0, 1_000_000, IN_SPK)] + plain_inputs(4), sorted_outputs(PLAIN))),
]

LABEL_FIXTURES = [
    ("h9_coinjoin_labelled_input", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 234_569)),
     lambda: add_utxo_label(TXID_A, 0, "whirlpool change", "coinjoin"),
     [{"label_type": "utxo", "txid": TXID_A, "vout": 0, "address": None,
       "label": "whirlpool change", "tag": "coinjoin"}]),
    ("h8_tainted_utxo_caps_score", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 234_569)),
     lambda: add_utxo_label(TXID_A, 0, "darknet withdrawal", "tainted"),
     [{"label_type": "utxo", "txid": TXID_A, "vout": 0, "address": None,
       "label": "darknet withdrawal", "tag": "tainted"}]),
    ("h8_clean_tag_does_not_fire", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 234_569)),
     lambda: add_utxo_label(TXID_A, 0, "my savings", "clean"),
     [{"label_type": "utxo", "txid": TXID_A, "vout": 0, "address": None,
       "label": "my savings", "tag": "clean"}]),
    ("h8_tx_level_label_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 234_569)),
     lambda: add_transaction_label(TXID_A, "exchange batch", "unknown"),
     [{"label_type": "tx", "txid": TXID_A, "vout": None, "address": None,
       "label": "exchange batch", "tag": "unknown"}]),
    ("h8_addr_level_label_fires", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)], sorted_outputs(PLAIN, 234_569)),
     lambda: add_address_label(script_to_address(IN_SPK), "kyc deposit addr", "kyc"),
     [{"label_type": "addr", "txid": None, "vout": None,
       "address": script_to_address(IN_SPK), "label": "kyc deposit addr", "tag": "kyc"}]),
]

URI_FIXTURES = [
    ("h11_pj_uri_two_inputs_info", "psbt",
     lambda: psbt(plain_inputs(2), sorted_outputs(PLAIN)), PJ_URI),
    ("h11_pj_uri_five_inputs_warning_with_h5", "psbt",
     lambda: psbt(plain_inputs(5), sorted_outputs(PLAIN)), PJ_URI),
    ("h11_uri_without_pj_passes", "psbt",
     lambda: psbt(plain_inputs(2), sorted_outputs(PLAIN)), "bitcoin:bc1qexample?amount=0.01"),
]

ENGINE_FIXTURES = [
    ("engine_multiple_findings_sum", "psbt",
     lambda: psbt([(TXID_A, 0, 2_345_678, IN_SPK)],
                  [(1_000_000, p2pkh(0xCC)), (PLAIN, OUT_SPK)], locktime=0)),
]


def fresh_db():
    labels_module.DB_PATH = Path(tempfile.mkdtemp()) / "labels.db"
    init_db()


def expected_of(report):
    return {
        "score": report.score,
        "findings": [
            {"id": f.heuristic_id, "severity": f.severity.value,
             "weight": f.weight, "positive": f.positive}
            for f in report.findings
        ],
        "checks": [{"id": c.heuristic_id, "status": c.status} for c in report.checks],
    }


def run(name, kind, build, labels=None, setup=None, bip21_uri=None):
    fresh_db()
    if setup:
        setup()
    tx, meta = parse_as(build(), kind, lookup=False)
    if bip21_uri:
        meta = {**meta, "payment_uri": bip21_uri}
    report = _score_parsed(tx, meta, lookup=False)
    return {
        "name": name,
        "input": build(),
        "input_type": kind,
        "labels": labels or [],
        "bip21_uri": bip21_uri,
        "expected": expected_of(report),
    }


vectors = [run(n, k, b) for n, k, b in FIXTURES]
vectors += [run(n, k, b, labels=recs, setup=setup) for n, k, b, setup, recs in LABEL_FIXTURES]
vectors += [run(n, k, b, bip21_uri=uri) for n, k, b, uri in URI_FIXTURES]
vectors += [run(n, k, b) for n, k, b in ENGINE_FIXTURES]

print(json.dumps(vectors, indent=2))
