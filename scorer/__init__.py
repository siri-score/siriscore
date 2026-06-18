"""utxo-privacy-scorer — public API."""
from scorer.parser import parse
from scorer.parser import parse_as
from scorer.report import Report, Finding, Severity, Check
from scorer.labels import init_db, import_sparrow
from scorer.heuristics import LOCAL as _LOCAL, NETWORK as _NETWORK
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

_NETWORK_IDS = {"H3", "H4"}


def score(
    input_str: str,
    lookup: bool | str = False,
    rpc_url: str | None = None,
    rpc_user: str | None = None,
    rpc_password: str | None = None,
) -> Report:
    """Score a PSBT (base64), raw tx hex, or txid.

    lookup=False (default): H1,H2,H5,H6,H7,H8 — zero network calls.
    lookup=True or lookup="mempool": also runs H3+H4 via mempool.space/blockstream.
    lookup="rpc": runs H4 via Bitcoin Core RPC; H3 skipped (no non-wallet address index).
      Requires rpc_url; rpc_user/rpc_password optional if node has no auth.
    """
    backend = _make_backend(lookup, rpc_url, rpc_user, rpc_password)
    run_network = bool(lookup) or (backend is not None)
    return _score_parsed(*parse(input_str), lookup=run_network, backend=backend)


def score_as(
    input_str: str,
    input_type: str,
    lookup: bool | str = False,
    rpc_url: str | None = None,
    rpc_user: str | None = None,
    rpc_password: str | None = None,
) -> Report:
    """Score input using an explicit type: psbt, rawtx, or txid."""
    backend = _make_backend(lookup, rpc_url, rpc_user, rpc_password)
    run_network = bool(lookup) or (backend is not None)
    return _score_parsed(*parse_as(input_str, input_type), lookup=run_network, backend=backend)


def _make_backend(lookup, rpc_url, rpc_user, rpc_password):
    if lookup == "rpc":
        if not rpc_url:
            raise ValueError("lookup='rpc' requires rpc_url")
        from scorer.rpc import RPCBackend
        return RPCBackend(url=rpc_url, user=rpc_user or "", password=rpc_password or "")
    return None


def _score_parsed(tx, psbt_meta, lookup: bool = False, backend=None) -> Report:
    init_db()

    heuristics = _LOCAL + (_NETWORK if lookup else [])

    meta = {**psbt_meta, "_backend": backend} if backend is not None else psbt_meta

    findings = []
    for module in heuristics:
        result = module.check(tx, meta)
        if result is not None:
            findings.append(result)

    raw_score = max(0, 100 - sum(f.weight for f in findings))

    tainted = any(f.heuristic_id == "H8" for f in findings)
    final_score = min(raw_score, _H8_SCORE_CAP) if tainted else raw_score
    checks = _build_checks(tx, findings, lookup, backend)

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


def _build_checks(tx, findings: list[Finding], lookup: bool, backend=None) -> list[Check]:
    findings_by_id = {f.heuristic_id: f for f in findings}
    # True when backend is an RPC node that has no non-wallet address index.
    no_address_index = backend is not None and not getattr(backend, "HAS_ADDRESS_INDEX", True)
    checks = []

    for heuristic_id, severity, title in _HEURISTIC_DEFS:
        finding = findings_by_id.get(heuristic_id)
        if finding is not None:
            checks.append(Check(heuristic_id, finding.severity, finding.title, "fail"))
            continue

        if heuristic_id in _NETWORK_IDS and not lookup:
            reason = _unavailable_reason(heuristic_id, tx)
            if reason:
                checks.append(Check(heuristic_id, severity, title, "unavailable", reason))
            else:
                checks.append(Check(heuristic_id, severity, title, "skipped",
                    "Pass lookup=True or --rpc-url to enable network checks"))
            continue

        # H3 requires an address-history index not available via non-wallet RPC.
        if heuristic_id == "H3" and no_address_index:
            checks.append(Check(heuristic_id, severity, title, "unavailable",
                "Address history unavailable via non-wallet RPC — use mempool backend for H3"))
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

    if heuristic_id == "H4" and not any(getattr(i, "script_pubkey", None) for i in tx.inputs):
        return "Input prevout data unavailable"

    if heuristic_id == "H6" and not any(getattr(i, "value", None) is not None for i in tx.inputs):
        return "Input values unavailable"

    return ""
