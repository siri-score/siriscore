from collections import Counter
from scorer.report import Finding, Severity

WHIRLPOOL_DENOMS = frozenset({100_000, 1_000_000, 5_000_000, 50_000_000})
MIN_PARTICIPANTS = 3
WASABI_MIN_PEERS = 5
COINJOIN_SCORE_BONUS = 10  # negative weight → adds to score


def check(tx, psbt_meta) -> Finding | None:
    if _is_whirlpool(tx):
        return _positive_finding("Whirlpool-style")
    if _is_wasabi(tx):
        return _positive_finding("Wasabi/WabiSabi-style")
    if _is_joinmarket(tx):
        return _positive_finding("JoinMarket-style")
    return None


def _is_whirlpool(tx) -> bool:
    if len(tx.inputs) < MIN_PARTICIPANTS or len(tx.outputs) < MIN_PARTICIPANTS:
        return False
    for denom in WHIRLPOOL_DENOMS:
        if sum(1 for o in tx.outputs if o.value == denom) >= MIN_PARTICIPANTS:
            return True
    return False


def _is_wasabi(tx) -> bool:
    if len(tx.inputs) < WASABI_MIN_PEERS or len(tx.outputs) < WASABI_MIN_PEERS:
        return False
    value_counts = Counter(o.value for o in tx.outputs)
    top_value, top_count = value_counts.most_common(1)[0]
    # Dominant equal-value output group, with enough inputs to fund participants
    return top_count >= WASABI_MIN_PEERS and len(tx.inputs) >= top_count


def _is_joinmarket(tx) -> bool:
    # JoinMarket: equal input and output count, 3+ distinct input scripts
    if len(tx.inputs) < MIN_PARTICIPANTS or len(tx.outputs) < MIN_PARTICIPANTS:
        return False
    if len(tx.inputs) != len(tx.outputs):
        return False
    scripts = {bytes(inp.script_pubkey) for inp in tx.inputs if getattr(inp, "script_pubkey", None)}
    return len(scripts) >= MIN_PARTICIPANTS


def _positive_finding(coinjoin_type: str) -> Finding:
    return Finding(
        heuristic_id="H10",
        severity=Severity.INFO,
        title="Transaction is a coinjoin",
        detail=(
            f"This transaction matches the {coinjoin_type} coinjoin fingerprint. "
            "Coinjoins break the Common Input Ownership Heuristic — analysts cannot "
            "determine which inputs belong to which participant."
        ),
        suggestion=(
            "No action needed — participating in a coinjoin is the strongest "
            "available on-chain privacy technique."
        ),
        weight=-COINJOIN_SCORE_BONUS,
        positive=True,
    )
