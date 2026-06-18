from scorer.report import Finding, Severity
from scorer.labels import get_input_label

TAINTED_SCORE_CAP = 40


def check(tx, psbt_meta) -> Finding | None:
    for inp in tx.inputs:
        record = get_input_label(inp.txid, inp.vout, inp.address)
        if record and _should_flag_label(record):
            tag = record.get("tag", "unknown")
            label_type = record.get("label_type", "utxo")
            tagged_tainted = tag == "tainted"
            return Finding(
                heuristic_id="H8",
                severity=Severity.CRITICAL,
                title="Labelled UTXO in inputs",
                detail=(
                    f"Input {inp.txid[:16]}…:{inp.vout} is labelled "
                    f'"{record["label"]}" via {label_type} label. '
                    f"{'It is tagged tainted. ' if tagged_tainted else 'Sparrow labels do not always include taint tags, but this labelled provenance is still sensitive. '}"
                    f"Maximum score is capped at {TAINTED_SCORE_CAP}."
                ),
                suggestion=(
                    "Review the label before spending this input with other coins. "
                    "Avoid mixing sensitive provenance with clean UTXOs."
                ),
                weight=25,
            )
    return None


def _should_flag_label(record: dict) -> bool:
    tag = (record.get("tag") or "unknown").lower()
    return tag not in {"clean", "coinjoin"}
