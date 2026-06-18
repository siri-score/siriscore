# SiriScore — Bitcoin Transaction Privacy Scorer

Pre-broadcast Bitcoin transaction privacy analysis. Accepts a PSBT, raw tx hex, or txid and returns a scored privacy report with actionable findings — before you sign.

## Setup

```bash
# Clone and install with dev dependencies
git clone <repo-url>
cd siriscore
pip install -e ".[dev]"
```

Requires Python 3.11+.

---

## Running the web UI

```bash
uvicorn api.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

Paste a PSBT, raw transaction hex, or txid into the text area and click **Analyse Transaction**. The page also works offline — open `web/index.html` directly in a browser and it uses built-in mock data with no server required.

To import coin labels from Sparrow Wallet, click **Import labels from Sparrow Wallet** and select your exported `.json` file.

---

## Running the CLI

```bash
# Score a PSBT
btc-privacy-check --psbt <base64>

# Score a raw transaction hex
btc-privacy-check --rawtx <hex>

# Score by txid (fetches from mempool.space)
btc-privacy-check --txid <txid>

# Import Sparrow labels before scoring
btc-privacy-check --psbt <b64> --import-sparrow sparrow-labels.json

# Fail with exit code 1 if score is below threshold (for CI)
btc-privacy-check --psbt <b64> --fail-below 60

# Machine-readable JSON output
btc-privacy-check --psbt <b64> --json
```

---

## Automated CI integration

Use `--fail-below` to gate a build on privacy score. The CLI uses distinct exit codes so CI can distinguish a bad score from a broken input:

| Exit code | Meaning |
|-----------|---------|
| 0 | Score is at or above the threshold (or no threshold set) |
| 1 | Score is below the `--fail-below` threshold |
| 2 | Parse error — invalid PSBT/hex/txid or network failure |

```bash
# Fail the build if privacy score is below 60
btc-privacy-check --psbt "$PSBT" --fail-below 60

# Machine-readable JSON output (useful for log parsing)
btc-privacy-check --psbt "$PSBT" --json

# Both flags together — JSON output, exit 1 if score < 60
btc-privacy-check --psbt "$PSBT" --fail-below 60 --json
```

Example GitHub Actions step:

```yaml
- name: Check transaction privacy
  run: btc-privacy-check --psbt "${{ env.PSBT }}" --fail-below 60 --json
```

On a parse error with `--json`, stdout is `{"error": "<reason>"}` and the exit code is 2, so scripts can distinguish it from a score failure.

---

## Using the library

```python
from utxo_privacy_scorer import score, import_labels

report = score("cHNidP8BA...")   # base64 PSBT, raw hex, or txid
print(report.score)              # 0–100
for f in report.findings:
    print(f.heuristic_id, f.severity.value, f.title)
    print(f"  {f.detail}")
    print(f"  Fix: {f.suggestion}")

# With coin labels — H8 fires if a tainted UTXO is present
import_labels("sparrow-labels.json", source="sparrow")
report = score("cHNidP8BA...")
```

Labels are stored in `~/.utxo-privacy-scorer/labels.db` (SQLite, local only).

---

## Running tests

```bash
# All tests
pytest

# Single file
pytest tests/test_labels.py

# Single test
pytest tests/test_heuristics.py::TestH2RoundAmount::test_fires_on_round_output

# With coverage
pytest --cov=scorer
```

---

## Heuristics

| ID | Heuristic | Severity | Weight |
|----|-----------|----------|--------|
| H1 | Script type mismatch | Critical | 25 |
| H2 | Round payment amount | Warning | 15 |
| H3 | Address reuse on input | Critical | 20 |
| H4 | UTXO age clustering | Warning | 10 |
| H5 | High input count (CIOH) | Warning | 10 |
| H6 | Dust input present | Warning | 10 |
| H7 | Non-BIP69 ordering | Info | 5 |
| H8 | Tainted labelled UTXO | Critical | 25 (cap 40) |

Score = 100 minus sum of triggered weights, floored at 0. H8 caps the final score at 40 regardless of other findings.
