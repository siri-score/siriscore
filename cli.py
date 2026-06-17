"""btc-privacy-check — CLI entry point."""
import argparse
import json
import sys

from rich.console import Console
from rich.text import Text

from scorer import score, import_labels
from scorer.report import Severity

console = Console()

SEVERITY_STYLES = {
    Severity.CRITICAL: ("red", "CRITICAL"),
    Severity.WARNING: ("yellow", "WARNING"),
    Severity.INFO: ("blue", "INFO"),
}

VERDICT = {
    range(0, 40): ("POOR", "red"),
    range(40, 70): ("FAIR", "yellow"),
    range(70, 101): ("GOOD", "green"),
}


def verdict(s: int):
    for r, (label, colour) in VERDICT.items():
        if s in r:
            return label, colour
    return "POOR", "red"


def main():
    parser = argparse.ArgumentParser(
        prog="btc-privacy-check",
        description="Pre-broadcast Bitcoin transaction privacy scorer",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--psbt", metavar="BASE64")
    group.add_argument("--rawtx", metavar="HEX")
    group.add_argument("--txid", metavar="TXID")
    parser.add_argument("--labels", metavar="DB_PATH")
    parser.add_argument("--import-sparrow", metavar="JSON_PATH")
    parser.add_argument("--fail-below", type=int, metavar="SCORE")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args()

    if args.import_sparrow:
        n = import_labels(args.import_sparrow)
        console.print(f"Imported {n} labels from {args.import_sparrow}")

    input_str = args.psbt or args.rawtx or args.txid
    report = score(input_str)

    if args.json_output:
        print(json.dumps({
            "score": report.score,
            "findings": [
                {
                    "id": f.heuristic_id,
                    "severity": f.severity.value,
                    "title": f.title,
                    "detail": f.detail,
                    "suggestion": f.suggestion,
                    "weight": f.weight,
                }
                for f in report.findings
            ],
            "checks": [
                {
                    "id": c.heuristic_id,
                    "severity": c.severity.value,
                    "title": c.title,
                    "status": c.status,
                    "reason": c.reason,
                }
                for c in report.checks
            ],
            "input_count": report.input_count,
            "output_count": report.output_count,
            "psbt_version": report.psbt_version,
        }, indent=2))
    else:
        label, colour = verdict(report.score)
        console.print(f"\nPrivacy Score: [{colour}]{report.score} / 100  [{label}][/{colour}]\n")

        for f in report.findings:
            style, name = SEVERITY_STYLES[f.severity]
            console.print(Text(f"{name:<10}", style=style), end="")
            console.print(f" {f.heuristic_id}  {f.title}")
            console.print(f"          {f.detail}")
            console.print(f"          [orange]Fix: {f.suggestion}[/orange]\n")

    if args.fail_below is not None and report.score < args.fail_below:
        sys.exit(1)


if __name__ == "__main__":
    main()
