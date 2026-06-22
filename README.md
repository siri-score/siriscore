# SiriScore — Bitcoin Transaction Privacy Scorer

Pre-broadcast Bitcoin transaction privacy analysis. Accepts a PSBT, raw tx hex, or txid and returns a scored privacy report with actionable findings — before you sign.

[![CI](https://github.com/nkatha23/siriscore/actions/workflows/ci.yml/badge.svg)](https://github.com/nkatha23/siriscore/actions/workflows/ci.yml)

---

## Requirements

- Python 3.11 or later
- Internet access is **optional** — H3 (address reuse) and H4 (UTXO age) require network lookups; all other heuristics are fully offline

---

## Installation

### From TestPyPI (current release)

```bash
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            siriscore
```

Package page: [https://test.pypi.org/project/siriscore/0.1.0/](https://test.pypi.org/project/siriscore/0.1.0/)

The `--extra-index-url pypi.org` flag lets pip pull the runtime dependencies (fastapi, rich, requests, etc.) from the main PyPI index, since they are not mirrored on TestPyPI.

### From source (development)

```bash
git clone https://github.com/nkatha23/siriscore.git
cd siriscore
pip install -e ".[dev]"
```

The `-e` flag installs in editable mode — changes to `scorer/`, `api/`, or `cli.py` take effect immediately without reinstalling.

---

## Web UI

### 1. Start the server

```bash
uvicorn api.main:app --reload
```

The server starts at [http://localhost:8000](http://localhost:8000). Keep this terminal open while you use the UI.

To bind to a specific port:

```bash
uvicorn api.main:app --reload --port 8080
```

### 2. Open the browser

Go to [http://localhost:8000](http://localhost:8000). You'll see the SiriScore input form.

### 3. Analyse a transaction

1. **Pick an input type** — use the **PSBT / Raw Tx / Txid** tabs to tell SiriScore what you're pasting
2. **Paste your transaction** — base64 PSBT, raw hex, or a 64-character txid
3. Click **Analyse Transaction**

The results panel shows:
- **Privacy Score** (0–100) with a colour gauge and verdict (Critical / Poor / Fair / Good / Excellent)
- **Findings** — heuristics that fired, with detail and a fix suggestion each
- **Checks** — every heuristic with its status (pass / fail / skipped / unavailable)
- **Coin labels** — any UTXO labels loaded from Sparrow Wallet
- **What to do next** — prioritised action list based on the findings

### 4. Network checks (H3 + H4)

By default the **Enable network checks** toggle is **on** when the backend is running. This allows the server to query [mempool.space](https://mempool.space) (with [blockstream.info](https://blockstream.info) as fallback) for:

| Heuristic | What it looks up | Why it matters |
|-----------|-----------------|----------------|
| H3 — Address reuse | Transaction history for each input address | Reusing an address links all past and future activity to one identity |
| H4 — UTXO age clustering | Block height each input was confirmed in | UTXOs confirmed within 6 blocks of each other suggest they come from the same wallet |

**To disable network checks:** uncheck the toggle before clicking Analyse. H3 and H4 will show as `skipped` in the Checks panel — no data leaves your machine.

> **Privacy note:** when network checks are enabled, input addresses and txids are sent to mempool.space/blockstream.info. Disable the toggle if you are scoring a transaction you have not yet broadcast and do not want any data to reach a third party.

### 5. Import Sparrow Wallet labels

Click **Import labels from Sparrow Wallet** and select a `.json` file exported from Sparrow. Labels are stored locally in `~/.utxo-privacy-scorer/labels.db` (SQLite — no cloud, no sync). If any input UTXO is tagged `tainted`, heuristic H8 fires and the score is capped at 40.

### 6. Glossary

Click **Learn** in the top-right navigation to open a slide-in panel with 12 Bitcoin privacy terms explained in plain language. Use the search box to filter terms.

---

### Offline demo (no server required)

```bash
open web/index.html          # macOS
xdg-open web/index.html      # Linux
start web/index.html         # Windows
```

The page detects it is running as a local file and switches to built-in mock data automatically. No backend, no network, no install needed. Useful for exploring the UI or sharing a demo.

---

## CLI

```bash
# Score a PSBT
btc-privacy-check --psbt <base64>

# Score a raw transaction hex
btc-privacy-check --rawtx <hex>

# Score by txid (fetches raw tx from mempool.space / blockstream.info)
btc-privacy-check --txid <txid>

# Import Sparrow Wallet labels before scoring
btc-privacy-check --psbt <b64> --import-sparrow sparrow-labels.json

# Fail with exit code 1 if score is below a threshold (CI use)
btc-privacy-check --psbt <b64> --fail-below 60

# Machine-readable JSON output
btc-privacy-check --psbt <b64> --json

# Both: JSON output and exit 1 if score < 60
btc-privacy-check --psbt <b64> --fail-below 60 --json
```

The `siriscore` alias works identically:

```bash
siriscore --psbt <b64>
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Scored at or above threshold (or no threshold set) |
| 1 | Score is below the `--fail-below` threshold |
| 2 | Parse error — invalid PSBT/hex/txid or network failure |

With `--json`, a parse error writes `{"error": "<reason>"}` to stdout so scripts can distinguish it from a score failure.

---

## CI integration

Gate a build on privacy score using `--fail-below`:

```yaml
- name: Check transaction privacy
  run: btc-privacy-check --psbt "${{ env.PSBT }}" --fail-below 60 --json
```

---

## Python library

```python
import siriscore

# Score a PSBT, raw tx hex, or txid — all offline by default
report = siriscore.score("cHNidP8BA...")

print(report.score)              # 0–100
print(report.input_count)        # number of inputs
print(report.output_count)       # number of outputs

for f in report.findings:
    print(f.heuristic_id, f.severity.value, f.title)
    print(f"  {f.detail}")
    print(f"  Fix: {f.suggestion}")

for c in report.checks:
    # status: "pass" | "fail" | "unavailable" | "skipped"
    print(c.heuristic_id, c.status, c.reason)
```

### Privacy-first by default

Network lookups (H3, H4) are **opt-out by default**. No address or txid is ever sent to a third party unless you explicitly request it:

```python
# Default — fully offline, H3/H4 skipped
report = siriscore.score("cHNidP8BA...")

# Opt in to network checks (queries mempool.space with blockstream.info fallback)
report = siriscore.score("cHNidP8BA...", lookup=True)
```

### Coin labels and H8

Labels are stored locally in `~/.utxo-privacy-scorer/labels.db` (SQLite — no cloud, no sync).

```python
# Import labels from a Sparrow Wallet export
n = siriscore.import_labels("sparrow-labels.json")
print(f"Imported {n} labels")

# Score — H8 fires if any input UTXO is labelled "tainted"
# H8 also caps the final score at 40 regardless of other findings
report = siriscore.score("cHNidP8BA...")
```

Label tags: `tainted` (triggers H8 score cap), `coinjoin`, `clean`, `unknown`.

### Explicit input type

```python
from siriscore import score_as

report = score_as("cHNidP8BA...", input_type="psbt")
report = score_as("0200000001...", input_type="rawtx")
report = score_as("a1b2c3...",    input_type="txid", lookup=True)
```

---

## REST API

Start the server:

```bash
uvicorn api.main:app --reload
```

### POST /score

```bash
curl -s -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{"input": "cHNidP8BA...", "input_type": "psbt", "lookup": false}' \
  | python3 -m json.tool
```

Request body:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input` | string | required | PSBT (base64), raw tx hex, or txid |
| `input_type` | string | `"psbt"` | `"psbt"`, `"rawtx"`, or `"txid"` |
| `lookup` | boolean | `true` | Enable H3/H4 network checks |

Response fields: `score`, `findings`, `checks`, `labels`, `input_count`, `output_count`, `psbt_version`.

### GET/POST /labels

Manage coin labels in the local SQLite store.

### POST /labels/import

Upload a Sparrow Wallet JSON export to bulk-import labels.

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

| ID | Name | Severity | Weight | Requires network |
|----|------|----------|--------|-----------------|
| H1 | Script type mismatch | Critical | 25 | No |
| H2 | Round payment amount | Warning | 15 | No |
| H3 | Address reuse on input | Critical | 20 | Yes |
| H4 | UTXO age clustering | Warning | 10 | Yes |
| H5 | High input count (CIOH) | Warning | 10 | No |
| H6 | Dust input present | Warning | 10 | No |
| H7 | Non-BIP69 ordering | Info | 5 | No |
| H8 | Tainted labelled UTXO | Critical | 25 | No |

**Score** = 100 − sum of triggered weights, floored at 0.  
**H8 cap**: when H8 fires the final score is additionally capped at 40, regardless of other heuristics.

### Check statuses

Each heuristic produces a check in the report, even when it does not fire:

| Status | Meaning |
|--------|---------|
| `pass` | Heuristic ran and found no issue |
| `fail` | Heuristic fired — finding recorded |
| `skipped` | Network check deliberately not run (`lookup=False`) |
| `unavailable` | Could not run — input data missing (e.g. no prevout info in PSBT) |

---

## Project structure

```
scorer/          ← standalone Python library
  __init__.py    ← public API: score(), score_as(), import_labels()
  report.py      ← data models: Severity, Finding, Check, Report
  parser.py      ← PSBT / raw tx / txid parser
  lookup.py      ← mempool.space + blockstream.info with in-process cache
  labels.py      ← SQLite label store
  heuristics/    ← one module per heuristic: check(tx, psbt_meta) → Finding | None
siriscore/       ← re-export shim (import siriscore == import scorer)
cli.py           ← argparse + rich CLI
api/main.py      ← FastAPI backend
web/
  index.html     ← HTML shell
  style.css      ← all styles (CSS tokens, layout, glossary, responsive)
  app.js         ← all JavaScript (fetch, render, glossary, mock fallback)
tests/           ← pytest suite
```

---

## Development

```bash
# Lint
ruff check scorer/ api/ tests/

# Type-check
mypy scorer/

# Build wheel
python3 -m build --wheel

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

Continuous integration runs on every push and pull request to `dev` and `main` via `.github/workflows/ci.yml` (tests → ruff → wheel build).
