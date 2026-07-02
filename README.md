# SiriScore — Bitcoin Transaction Privacy Scorer

Pre-broadcast Bitcoin transaction privacy analysis. Paste a PSBT, raw tx hex, or txid and get a scored privacy report with actionable findings — before you sign.

[![CI](https://github.com/siri-score/siriscore/actions/workflows/ci.yml/badge.svg)](https://github.com/siri-score/siriscore/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/siriscore)](https://pypi.org/project/siriscore/)

**Live tool:** [siriscore.xyz](https://siriscore.xyz) · **Full docs:** [docs.siriscore.xyz](https://docs.siriscore.xyz)

---

## Install

```bash
pip install siriscore
```

## Library

```python
import siriscore

report = siriscore.score("cHNidP8BA...")  # PSBT, raw hex, or txid
print(report.score)          # 0–100
for f in report.findings:
    print(f.heuristic_id, f.severity.value, f.title)
```

## CLI

```bash
btc-privacy-check --txid <txid>
btc-privacy-check --psbt <base64>
btc-privacy-check --rawtx <hex>
```

Point at your own node (no data sent to third parties):

```bash
btc-privacy-check --txid <txid> \
  --rpc-url http://127.0.0.1:8332 \
  --rpc-user alice \
  --rpc-password hunter2
```

## Web UI

```bash
uvicorn api.main:app --reload
# open http://localhost:8000
```

---

## Heuristics

Eleven privacy checks across two categories:

| Category | IDs | What they catch |
|----------|-----|----------------|
| Penalty  | H1–H8 | Script mismatch, round amounts, address reuse, UTXO age clustering, high input count, dust, non-BIP69 ordering, tainted labels |
| Positive | H9–H11 | Coinjoin inputs, coinjoin structure (+10 score bonus), Payjoin opportunity |

Full heuristic reference at [docs.siriscore.xyz/heuristics](https://docs.siriscore.xyz/heuristics).

---

## Contributing

```bash
# Fork on GitHub, then:
git clone https://github.com/<your-username>/siriscore.git
cd siriscore
git remote add upstream https://github.com/siri-score/siriscore.git
pip install -e ".[dev]"

# Create a branch
git checkout -b feature/issue-42/your-description

# Test and lint
python3 -m pytest -q
ruff check scorer/ api/ tests/

# Open a PR to dev
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide including how to add a new heuristic.

---

## License

MIT
