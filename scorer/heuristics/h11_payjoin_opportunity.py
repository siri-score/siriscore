from urllib.parse import urlparse, parse_qs
from scorer.report import Finding, Severity

# Mirror h5_consolidation threshold so H11 can detect when H5 would fire
_H5_INPUT_THRESHOLD = 5


def check(tx, psbt_meta) -> Finding | None:
    uri = psbt_meta.get("payment_uri") or psbt_meta.get("bip21_uri")
    if not uri:
        return None

    pj_url = _extract_pj_endpoint(str(uri))
    if not pj_url:
        return None

    h5_fires = len(tx.inputs) >= _H5_INPUT_THRESHOLD

    if h5_fires:
        return Finding(
            heuristic_id="H11",
            severity=Severity.WARNING,
            title="Payjoin available — fixes H5 CIOH risk",
            detail=(
                f"This recipient supports Payjoin (BIP-77) at {pj_url[:70]}. "
                f"Your transaction uses {len(tx.inputs)} inputs (H5 fired). "
                "A Payjoin adds recipient inputs to the transaction, breaking the "
                "common-input-ownership assumption and eliminating the H5 signal entirely."
            ),
            suggestion=(
                "Use your wallet's BIP-77 Payjoin support to send a Payjoin instead. "
                "This resolves H5 and improves privacy for both you and the recipient."
            ),
            weight=0,
            positive=True,
        )

    return Finding(
        heuristic_id="H11",
        severity=Severity.INFO,
        title="Payjoin opportunity available",
        detail=(
            f"This recipient supports Payjoin (BIP-77) at {pj_url[:70]}. "
            "Initiating a Payjoin would break the common-input-ownership assumption "
            "and improve both parties' privacy."
        ),
        suggestion=(
            "Use your wallet's BIP-77 Payjoin support to send a Payjoin instead "
            "of a standard transaction."
        ),
        weight=0,
        positive=True,
    )


def _extract_pj_endpoint(uri: str) -> str | None:
    try:
        # BIP-21: bitcoin:ADDRESS?amount=X&pj=https://...
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        pj = params.get("pj")
        if pj:
            return pj[0]
    except Exception:
        pass
    return None
