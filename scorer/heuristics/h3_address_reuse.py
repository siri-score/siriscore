from scorer.report import Finding, Severity
from scorer.lookup import get_address_txs
from scorer.parser import script_to_address
from scorer.utils import is_silent_payment_address

MAX_ADDRESS_LOOKUPS = 5


def _output_supports_sp(tx) -> bool:
    return any(
        is_silent_payment_address(addr)
        for out in tx.outputs
        if (addr := script_to_address(out.script_pubkey))
    )


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
            if _output_supports_sp(tx):
                suggestion = (
                    "Recipient supports silent payments. Future payments to this "
                    "recipient will not reuse addresses."
                )
            else:
                suggestion = (
                    "Never reuse addresses. Generate a fresh address per receive. "
                    "Consider requesting a silent payment address from this recipient "
                    "to eliminate address reuse permanently."
                )
            return Finding(
                heuristic_id="H3",
                severity=Severity.CRITICAL,
                title="Address reuse on input",
                detail=(
                    f"Input address {address[:16]}… was previously used in "
                    f"{len(txs)} transactions. Reuse links all activity to one identity."
                ),
                suggestion=suggestion,
                weight=20,
            )
    return None
