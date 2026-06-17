from scorer.report import Finding, Severity


def check(tx, psbt_meta) -> Finding | None:
    input_types = {
        script_type
        for script_type in (classify_script(i.script_pubkey) for i in tx.inputs)
        if script_type != "unknown"
    }
    output_types = {
        script_type
        for script_type in (classify_script(o.script_pubkey) for o in tx.outputs)
        if script_type != "unknown"
    }

    if len(input_types) == 1 and output_types - input_types:
        mismatched = output_types - input_types
        return Finding(
            heuristic_id="H1",
            severity=Severity.CRITICAL,
            title="Script type mismatch",
            detail=(
                f"Inputs are {list(input_types)[0]}. "
                f"Output(s) use {mismatched}. "
                f"Change output is trivially identifiable."
            ),
            suggestion=(
                "Ensure all outputs use the same script type as inputs, "
                "or match the recipient's script type."
            ),
            weight=25,
        )
    return None


def classify_script(script_pubkey) -> str:
    script = bytes(script_pubkey or b"")

    if len(script) == 25 and script[:3] == b"\x76\xa9\x14" and script[-2:] == b"\x88\xac":
        return "p2pkh"

    if len(script) == 23 and script[:2] == b"\xa9\x14" and script[-1:] == b"\x87":
        return "p2sh"

    if len(script) == 22 and script[:2] == b"\x00\x14":
        return "p2wpkh"

    if len(script) == 34 and script[:2] == b"\x00\x20":
        return "p2wsh"

    if len(script) == 34 and script[:2] == b"\x51\x20":
        return "p2tr"

    return "unknown"
