"""H12 — Silent Payments recommendation (BIP-352), fires when H3 fires."""
from scorer.lookup import get_address_txs
from scorer.parser import script_to_address
from scorer.report import Finding, Severity
from scorer.utils import is_silent_payment_address

MAX_ADDRESS_LOOKUPS = 5


def _address_is_reused(address: str, get_fn) -> bool:
    try:
        return len(get_fn(address)) > 1
    except Exception:  # noqa: BLE001, S112
        return False


def _output_supports_sp(tx) -> bool:
    return any(
        is_silent_payment_address(addr)
        for out in tx.outputs
        if (addr := script_to_address(out.script_pubkey))
    )


def check(tx, psbt_meta) -> Finding | None:
    backend = psbt_meta.get("_backend")
    _get = backend.get_address_txs if backend else get_address_txs

    reuse_found = False
    checked = 0
    for inp in tx.inputs:
        address = inp.address
        if not address or checked >= MAX_ADDRESS_LOOKUPS:
            continue
        checked += 1
        if _address_is_reused(address, _get):
            reuse_found = True
            break

    if not reuse_found:
        return None

    if _output_supports_sp(tx):
        detail = "Recipient already uses silent payments — future payments will not reuse addresses."
        suggestion = (
            "No action needed. The recipient's silent payment address ensures "
            "every payment lands at a unique on-chain address automatically."
        )
    else:
        detail = (
            "Address reuse detected. The recipient does not appear to use silent payments."
        )
        suggestion = (
            "Consider requesting a silent payment address (BIP-352) from this recipient. "
            "Silent payments eliminate address reuse permanently — no coordination required."
        )

    return Finding(
        heuristic_id="H12",
        severity=Severity.INFO,
        title="Silent payments recommendation",
        detail=detail,
        suggestion=suggestion,
        weight=0,
    )
