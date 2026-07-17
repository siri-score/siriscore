from scorer.report import Finding, Severity

RBF_SEQUENCE_THRESHOLD = 0xFFFFFFFD


def check(tx, psbt_meta) -> Finding | None:
    if not tx.inputs:
        return None

    signals = [inp.sequence <= RBF_SEQUENCE_THRESHOLD for inp in tx.inputs]

    if all(signals):
        return Finding(
            heuristic_id="H14",
            severity=Severity.INFO,
            title="Replace-By-Fee (RBF) Signalling Fingerprint",
            detail=(
                "All inputs signal Replace-By-Fee (nSequence <= 0xfffffffd). "
                "Uniform RBF signalling is consistent, but the specific choice is "
                "still a minor wallet fingerprint."
            ),
            suggestion="No action needed — signalling is consistent across inputs.",
            weight=0,
            positive=True,
        )

    if not any(signals):
        return Finding(
            heuristic_id="H14",
            severity=Severity.INFO,
            title="Replace-By-Fee (RBF) Signalling Fingerprint",
            detail=(
                "No inputs signal Replace-By-Fee (nSequence > 0xfffffffd). "
                "The absence of RBF signalling is also a wallet fingerprint."
            ),
            suggestion="No action needed — signalling is consistent across inputs.",
            weight=0,
            positive=True,
        )

    return Finding(
        heuristic_id="H14",
        severity=Severity.WARNING,
        title="Replace-By-Fee (RBF) Signalling Fingerprint",
        detail=(
            "Inputs disagree on Replace-By-Fee signalling — some have "
            "nSequence <= 0xfffffffd and others do not. Mixed signalling is "
            "unusual and can fingerprint the wallet or hint at multiple "
            "co-signers/sources."
        ),
        suggestion="Use a wallet that sets nSequence consistently across all inputs.",
        weight=5,
    )
