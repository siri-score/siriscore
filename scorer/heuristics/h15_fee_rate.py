from scorer.heuristics.h1_script_mismatch import classify_script
from scorer.report import Finding, Severity

ROUND_FEE_RATES = {1, 2, 5, 10, 20, 50, 100}  # sat/vbyte

# Rough per-item vbyte costs by script type, used only to estimate vsize when
# no signed/witness data is available (e.g. an unsigned PSBT).
_INPUT_VSIZE = {"p2pkh": 148, "p2sh": 91, "p2wpkh": 68, "p2wsh": 104, "p2tr": 58}
_OUTPUT_VSIZE = {"p2pkh": 34, "p2sh": 32, "p2wpkh": 31, "p2wsh": 43, "p2tr": 43}
_DEFAULT_INPUT_VSIZE = 148
_DEFAULT_OUTPUT_VSIZE = 34
_OVERHEAD_VSIZE = 11  # version + locktime + input/output count varints


def check(tx, psbt_meta) -> Finding | None:
    if not tx.inputs or any(inp.value is None for inp in tx.inputs):
        return None

    fee = sum(inp.value for inp in tx.inputs) - sum(out.value for out in tx.outputs)
    fee_rate = fee / _estimate_vsize(tx)

    rounded = round(fee_rate)
    if abs(fee_rate - rounded) > 0.01 or rounded not in ROUND_FEE_RATES:
        return None

    return Finding(
        heuristic_id="H15",
        severity=Severity.INFO,
        title="Fee Rate Fingerprint",
        detail=(
            f"Fee rate of {rounded} sat/vbyte is a round number. Some wallets "
            "default to round fee rates, which can fingerprint the wallet "
            "software used."
        ),
        suggestion="Use a wallet with dynamic fee estimation (mempool-based) rather than round defaults.",
        weight=5,
    )


def _estimate_vsize(tx) -> int:
    total = _OVERHEAD_VSIZE
    for inp in tx.inputs:
        total += _INPUT_VSIZE.get(classify_script(inp.script_pubkey), _DEFAULT_INPUT_VSIZE)
    for out in tx.outputs:
        total += _OUTPUT_VSIZE.get(classify_script(out.script_pubkey), _DEFAULT_OUTPUT_VSIZE)
    return total
