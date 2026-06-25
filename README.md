# SiriScore — Bitcoin Transaction Privacy Scorer

Pre-broadcast Bitcoin transaction privacy analysis. Accepts a PSBT, raw tx hex, or txid and returns a scored privacy report with actionable findings — before you sign.

[![CI](https://github.com/nkatha23/siriscore/actions/workflows/ci.yml/badge.svg)](https://github.com/nkatha23/siriscore/actions/workflows/ci.yml)

---

## Requirements

- Python 3.11 or later
- Internet access is **optional** — H3 (address reuse) and H4 (UTXO age) require network lookups; all other heuristics are fully offline

---

## Installation

### From PyPI

```bash
pip install siriscore
```

Package page: [https://pypi.org/project/siriscore/](https://pypi.org/project/siriscore/)

### From source (development)

```bash
git clone https://github.com/nkatha23/siriscore.git
cd siriscore
pip install -e ".[dev]"



OR

python3 -m pip install -e ".[dev]"
```

The `-e` flag installs in editable mode — changes to `scorer/`, `api/`, or `cli.py` take effect immediately without reinstalling.

---

## Web UI

### 1. Start the server

```bash
uvicorn api.main:app --reload

OR

python3 -m uvicorn api.main:app --reload
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

To import coin labels from Sparrow Wallet, click **Import labels from Sparrow Wallet** and select your exported `.jsonl` labels file.

Sparrow label import supports Sparrow Wallet v1.8+ BIP329 JSONL exports (`type` + `ref` + `label` records), including transaction (`tx`), address (`addr`), and UTXO (`output`/`input`) labels. It also keeps backward compatibility with the older simple `{"txid:vout": "label"}` JSON shape used by early SiriScore fixtures. The parser is covered by local fixtures based on Sparrow's BIP329 JSONL format and cross-checked against Sparrow Wallet 2.5.2's `WalletLabels` export implementation.

---

## Testing Sparrow label import

### Option A — use a sample labels file

Create `sparrow-labels.jsonl`:

```jsonl
{"type":"tx","ref":"93c98c2a742373460e74b7d3b39ba30283b14476df835916d0a3f60dfc988e0d","label":"Exchange withdrawal","tag":"tainted"}
{"type":"addr","ref":"bc1qalum72s7tmt39y32fv5r06qvu9nz5phdjfcw8h","label":"KYC receive address","tag":"tainted"}
{"type":"output","ref":"35cebb10f6d6129716effcd69eb43df40669f4b27533be0857299fec0c52a976:1","label":"Specific labelled coin","tag":"tainted"}
```

Run the dashboard:

```bash
python3 -m uvicorn api.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000), click **Import labels from Sparrow Wallet**, select `sparrow-labels.jsonl`, paste this txid, and analyse:

```text
93c98c2a742373460e74b7d3b39ba30283b14476df835916d0a3f60dfc988e0d
```

Expected result: H8 fires because this transaction spends inputs matching the imported transaction, address, or UTXO labels.

### Option B — export labels from a real Sparrow wallet

Use a tiny test amount only. A Sparrow software wallet is fine for testing, but do not treat a quick test wallet as long-term secure storage.

1. Download Sparrow from the official site and verify the download if you can: [https://sparrowwallet.com/docs/](https://sparrowwallet.com/docs/)
2. Open Sparrow and choose a server connection. For testing, a public server is easiest, but it reduces privacy because wallet public key information is shared with the server.
3. Click **Create New Wallet**.
4. Enter a wallet name, for example `siriscore-test`.
5. Use the defaults: **Single Signature** and **Native Segwit (P2WPKH)**.
6. Choose **New or Imported Software Wallet**.
7. Create a BIP39 mnemonic, for example 12 words.
8. Finish setup and click **Apply**.

Add labels in Sparrow:

- Address label: go to **Addresses** or **Receive**, pick a receive address, and add a label such as `KYC test receive address`.
- Transaction label: after receiving a tiny amount, go to **Transactions** and label the transaction, for example `Test transaction label`.
- UTXO label: go to **UTXOs** and label the coin, for example `Specific labelled coin`.

Export the wallet labels from Sparrow. The modern export format is BIP329 JSONL, one JSON object per line:

```jsonl
{"type":"tx","ref":"<txid>","label":"Test transaction label"}
{"type":"addr","ref":"bc1q...","label":"KYC test receive address"}
{"type":"output","ref":"<txid>:0","label":"Specific labelled coin"}
```

Import the `.jsonl` file into SiriScore, then paste either a txid from Sparrow's **Transactions** tab or a PSBT exported from Sparrow. A PSBT is the best test because it carries richer input metadata.

Expected result: if the transaction spends a labelled input, H8 fires and the **Coin labels** section shows only labels relevant to the analysed transaction inputs.

For example, if you label `35ce...:1` and analyse `93c98c...`, it should match because `93c98c...` spends output `35ce...:1`. If you analyse `35ce...` itself, that label may not match because `35ce...:1` is an output of that transaction, not an input being spent by it.

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

# Import Sparrow labels before scoring
btc-privacy-check --psbt <b64> --import-sparrow sparrow-labels.jsonl

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

# With coin labels — H8 fires if a tainted UTXO, transaction, or address label matches an input
import_labels("sparrow-labels.jsonl", source="sparrow")
report = score("cHNidP8BA...")
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
python3 -m pytest

# Single file
python3 -m pytest tests/test_labels.py

# Single test
python3 -m pytest tests/test_heuristics.py::TestH2RoundAmount::test_fires_on_round_output

# With coverage
python3 -m pytest --cov=scorer
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
