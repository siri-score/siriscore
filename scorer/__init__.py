"""utxo-privacy-scorer — public API."""
from scorer.parser import parse
from scorer.parser import parse_as
from scorer.report import Report, Finding, Severity, Check
from scorer.labels import init_db, import_sparrow
from scorer.heuristics import ALL as _HEURISTICS
from scorer.heuristics.h1_script_mismatch import classify_script

_H8_SCORE_CAP = 40

_HEURISTIC_DEFS = [
    ("H1", Severity.CRITICAL, "Script type mismatch"),
    ("H2", Severity.WARNING, "Round payment amount"),
    ("H3", Severity.CRITICAL, "Address reuse on input"),
    ("H4", Severity.WARNING, "UTXO age clustering"),
    ("H5", Severity.WARNING, "High input count consolidation"),
    ("H6", Severity.WARNING, "Dust input present"),
    ("H7", Severity.INFO, "Non-BIP69 input/output ordering"),
    ("H8", Severity.CRITICAL, "Labelled tainted UTXO in inputs"),
]


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
    checks = _build_checks(tx, findings)

    return Report(
        score=final_score,
        findings=findings,
        checks=checks,
        input_count=len(tx.inputs),
        output_count=len(tx.outputs),
        psbt_version=psbt_meta.get("version", 0),
    )


def import_labels(json_path: str, source: str = "sparrow") -> int:
    """Import labels from a Sparrow Wallet JSON export. Returns count imported."""
    init_db()
    return import_sparrow(json_path)


def _build_checks(tx, findings: list[Finding]) -> list[Check]:
    findings_by_id = {f.heuristic_id: f for f in findings}
    checks = []

    for heuristic_id, severity, title in _HEURISTIC_DEFS:
        finding = findings_by_id.get(heuristic_id)
        if finding is not None:
            checks.append(Check(heuristic_id, finding.severity, finding.title, "fail"))
            continue

        reason = _unavailable_reason(heuristic_id, tx)
        status = "unavailable" if reason else "pass"
        checks.append(Check(heuristic_id, severity, title, status, reason))

    return checks


def _unavailable_reason(heuristic_id: str, tx) -> str:
    if heuristic_id == "H1":
        has_known_input = any(classify_script(i.script_pubkey) != "unknown" for i in tx.inputs)
        has_known_output = any(classify_script(o.script_pubkey) != "unknown" for o in tx.outputs)
        if not has_known_input:
            return "Input script types unavailable"
        if not has_known_output:
            return "Output script types unavailable"

    if heuristic_id == "H3" and not any(getattr(i, "address", None) for i in tx.inputs):
        return "Input addresses unavailable"

    if heuristic_id == "H6" and not any(getattr(i, "value", None) is not None for i in tx.inputs):
        return "Input values unavailable"

    return ""
