# SiriScore — Bitcoin Transaction Privacy Scorer

Pre-broadcast Bitcoin transaction privacy analysis. Accepts a PSBT, raw tx hex, or txid and returns a scored privacy report with actionable findings — before you sign.

## Setup

```bash
# Clone and install with dev dependencies
git clone <repo-url>
cd siriscore
pip install -e ".[dev]"



OR

python3 -m pip install -e ".[dev]"
```

Requires Python 3.11+.

---

## Running the web UI

```bash
uvicorn api.main:app --reload

OR

python3 -m uvicorn api.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

Paste a PSBT, raw transaction hex, or txid into the text area and click **Analyse Transaction**. The page also works offline — open `web/index.html` directly in a browser and it uses built-in mock data with no server required.

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

## Running the CLI

```bash
# Score a PSBT
btc-privacy-check --psbt <base64>

# Score a raw transaction hex
btc-privacy-check --rawtx <hex>

# Score by txid (fetches from mempool.space)
btc-privacy-check --txid <txid>

# Import Sparrow labels before scoring
btc-privacy-check --psbt <b64> --import-sparrow sparrow-labels.jsonl

# Fail with exit code 1 if score is below threshold (for CI)
btc-privacy-check --psbt <b64> --fail-below 60

# Machine-readable JSON output
btc-privacy-check --psbt <b64> --json
```

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

# With coin labels — H8 fires if a tainted UTXO, transaction, or address label matches an input
import_labels("sparrow-labels.jsonl", source="sparrow")
report = score("cHNidP8BA...")
```

Labels are stored in `~/.utxo-privacy-scorer/labels.db` (SQLite, local only).

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
