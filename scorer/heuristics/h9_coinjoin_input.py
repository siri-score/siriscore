from scorer.report import Finding, Severity
from scorer.labels import get_input_label

WHIRLPOOL_DENOMS = frozenset({100_000, 1_000_000, 5_000_000, 50_000_000})


def check(tx, psbt_meta) -> Finding | None:
    for inp in tx.inputs:
        # Label store takes precedence — user-confirmed coinjoin tag
        record = get_input_label(inp.txid, inp.vout, getattr(inp, "address", None))
        if record and (record.get("tag") or "").lower() == "coinjoin":
            return Finding(
                heuristic_id="H9",
                severity=Severity.INFO,
                title="Input is a labelled coinjoin output",
                detail=(
                    f"Input {inp.txid[:16]}…:{inp.vout} is labelled as a coinjoin output. "
                    "The Common Input Ownership Heuristic (CIOH) does not apply — "
                    "analysts cannot attribute this coin to a single wallet."
                ),
                suggestion="No action needed — spending coinjoin outputs is privacy-positive.",
                weight=0,
                positive=True,
            )
        # Whirlpool denomination fingerprint (requires prevout value from PSBT)
        if getattr(inp, "value", None) in WHIRLPOOL_DENOMS:
            return Finding(
                heuristic_id="H9",
                severity=Severity.INFO,
                title="Input is a coinjoin output",
                detail=(
                    f"Input {inp.txid[:16]}…:{inp.vout} has value {inp.value:,} sats, "
                    "matching a Whirlpool pool denomination (100k / 1M / 5M / 50M sats). "
                    "The CIOH does not apply to coinjoin outputs."
                ),
                suggestion="No action needed — spending coinjoin outputs is privacy-positive.",
                weight=0,
                positive=True,
            )
    return None
