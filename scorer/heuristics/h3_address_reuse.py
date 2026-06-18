from scorer.report import Finding, Severity
from scorer.lookup import get_address_txs

MAX_ADDRESS_LOOKUPS = 5


def check(tx, psbt_meta) -> Finding | None:
    backend = psbt_meta.get("_backend")
    _get = backend.get_address_txs if backend else get_address_txs
    checked = 0
    for inp in tx.inputs:
        address = inp.address
        if not address or checked >= MAX_ADDRESS_LOOKUPS:
            continue
        checked += 1
        try:
            txs = _get(address)
        except Exception:
            continue
        if len(txs) > 1:
            return Finding(
                heuristic_id="H3",
                severity=Severity.CRITICAL,
                title="Address reuse on input",
                detail=(
                    f"Input address {address[:16]}… was previously used in "
                    f"{len(txs)} transactions. Reuse links all activity to one identity."
                ),
                suggestion="Never reuse addresses. Generate a fresh address per receive.",
                weight=20,
            )
    return None
