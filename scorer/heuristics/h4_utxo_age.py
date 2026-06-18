from scorer.report import Finding, Severity
from scorer.lookup import get_utxo_block_height

NARROW_RANGE = 6  # blocks — inputs within this range suggest clustering
MAX_UTXO_HEIGHT_LOOKUPS = 8


def check(tx, psbt_meta) -> Finding | None:
    if len(tx.inputs) < 2:
        return None

    backend = psbt_meta.get("_backend")
    _get = backend.get_utxo_block_height if backend else get_utxo_block_height
    heights = []
    seen_txids = set()
    for inp in tx.inputs:
        if len(seen_txids) >= MAX_UTXO_HEIGHT_LOOKUPS or inp.txid in seen_txids:
            continue
        seen_txids.add(inp.txid)
        try:
            h = _get(inp.txid)
        except Exception:
            continue
        if h is not None:
            heights.append(h)

    if len(heights) >= 2 and max(heights) - min(heights) <= NARROW_RANGE:
        return Finding(
            heuristic_id="H4",
            severity=Severity.WARNING,
            title="UTXO age clustering",
            detail=(
                f"All {len(heights)} inputs were confirmed within {NARROW_RANGE} blocks "
                "of each other. This suggests they came from the same source event."
            ),
            suggestion="Mix UTXOs from different time periods to break clustering.",
            weight=10,
        )
    return None
