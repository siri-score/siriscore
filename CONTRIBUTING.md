# Contributing to SiriScore

## Getting started

Fork the repo on GitHub, then clone your fork:

```bash
git clone https://github.com/<your-username>/siriscore.git
cd siriscore
git remote add upstream https://github.com/siri-score/siriscore.git
pip install -e ".[dev]"
```

Keep your fork in sync:

```bash
git fetch upstream
git rebase upstream/dev
```

## Branch naming

```
feature/issue-42/short-description
fix/issue-17/lookup-timeout
docs/update-heuristics-table
```

All PRs target the `dev` branch. `main` is release-only.

## Running tests

```bash
python3 -m pytest -q
```

Single file or test:

```bash
python3 -m pytest tests/test_heuristics.py -q
python3 -m pytest tests/test_heuristics.py::TestH2RoundAmount::test_fires_on_round_output -q
```

With coverage:

```bash
python3 -m pytest --cov=scorer -q
```

## Linting

```bash
ruff check scorer/ api/ tests/
```

Fix automatically:

```bash
ruff check --fix scorer/ api/ tests/
```

## PR process

1. Open a PR against `dev` (not `main`)
2. CI must pass (tests + ruff + wheel build)
3. One approval required
4. Squash-merge preferred for small changes; merge commit for large features

## Adding a new heuristic

1. Create `scorer/heuristics/hN_name.py` with a single `check` function:

```python
from scorer.report import Finding, Severity

def check(tx, psbt_meta) -> Finding | None:
    # tx has: .inputs, .outputs, .version, .locktime
    # psbt_meta is a dict of optional metadata
    if <condition>:
        return Finding(
            heuristic_id="HN",
            severity=Severity.WARNING,
            title="Short title",
            detail="What was found in this transaction.",
            suggestion="What the user should do about it.",
            weight=10,          # penalty weight; use negative for a bonus
            positive=False,     # True for privacy-positive findings (H9/H10/H11)
        )
    return None
```

2. Add it to `LOCAL` (or `NETWORK` if it makes outbound calls) in `scorer/heuristics/__init__.py`:

```python
from scorer.heuristics import hN_name
LOCAL = [..., hN_name]
```

3. Add an entry to `_HEURISTIC_DEFS` in `scorer/__init__.py`:

```python
("HN", Severity.WARNING, "Short title"),
```

4. Add tests in `tests/test_heuristics.py` — at minimum one test that fires and one that does not.

5. Update the heuristics overview table in the docs.

## Code owners

| Area | Owner |
|------|-------|
| `scorer/heuristics/` | open |
| `scorer/lookup.py` | open |
| `api/` | open |
| `web/` | open |
| CI / packaging | @nkatha23 |
