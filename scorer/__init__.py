"""utxo-privacy-scorer — public API."""
from scorer.parser import parse
from scorer.parser import parse_as
from scorer.report import Report, Finding, Severity
from scorer.labels import init_db, import_sparrow
from scorer.heuristics import ALL as _HEURISTICS

_H8_SCORE_CAP = 40


def score(input_str: str) -> Report:
    """Score a PSBT (base64), raw tx hex, or txid. Returns a Report."""
    return _score_parsed(*parse(input_str))


def score_as(input_str: str, input_type: str) -> Report:
    """Score input using an explicit type: psbt, rawtx, or txid."""
    return _score_parsed(*parse_as(input_str, input_type))


def _score_parsed(tx, psbt_meta) -> Report:
    init_db()

    findings = []
    for module in _HEURISTICS:
        result = module.check(tx, psbt_meta)
        if result is not None:
            findings.append(result)

    raw_score = max(0, 100 - sum(f.weight for f in findings))

    tainted = any(f.heuristic_id == "H8" for f in findings)
    final_score = min(raw_score, _H8_SCORE_CAP) if tainted else raw_score

    return Report(
        score=final_score,
        findings=findings,
        input_count=len(tx.inputs),
        output_count=len(tx.outputs),
        psbt_version=psbt_meta.get("version", 0),
    )


def import_labels(json_path: str, source: str = "sparrow") -> int:
    """Import labels from a Sparrow Wallet JSON export. Returns count imported."""
    init_db()
    return import_sparrow(json_path)
