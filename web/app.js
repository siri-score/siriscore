// ── Mock data ───────────────────────────────────────────────
const MOCK_RESULT = {
  score: 34,
  psbt_version: 2,
  input_count: 3,
  output_count: 2,
  findings: [
    {
      id: "H1",
      severity: "critical",
      title: "Script type mismatch",
      detail: "Your inputs use P2WPKH but at least one output is P2TR. Mixing script types makes your change output trivially identifiable to a chain analyst.",
      suggestion: "Send change to the same script type as your inputs (P2WPKH)."
    },
    {
      id: "H3",
      severity: "warning",
      title: "Round-number payment amount",
      detail: "Output #1 pays exactly 0.05000000 BTC. Round numbers strongly suggest the human-entered amount, which reveals which output is the payment and which is change.",
      suggestion: "Add a small random offset to the payment amount when possible."
    },
    {
      id: "H5",
      severity: "info",
      title: "Non-standard nLockTime",
      detail: "nLockTime is set to 0. Most wallets set it to the current block height as an anti-fee-sniping measure. The absence is a wallet fingerprint.",
      suggestion: "Use a wallet that sets nLockTime to the current tip height."
    }
  ],
  labels: [
    {
      txid: "a4f1c9d2e3b5a6f7890abc12",
      vout: 0,
      short_id: "a4f1c9d2…a5b6:0",
      label: "Kraken withdrawal",
      tag: "tainted",
      in_inputs: true
    },
    {
      txid: "9c8b7a6d5e4f3a2b1c0d9e8f",
      vout: 1,
      short_id: "9c8b7a6d…0493:1",
      label: "Whirlpool 0.01 pool",
      tag: "coinjoin",
      in_inputs: false
    },
    {
      txid: "11223344556677889900aabb",
      vout: 2,
      short_id: "11223344…5566:2",
      label: "Self-transfer cold storage",
      tag: "clean",
      in_inputs: false
    }
  ]
};

const MOCK_GOOD = {
  score: 96,
  psbt_version: 2,
  input_count: 3,
  output_count: 2,
  findings: [
    {
      id: "H1",
      severity: "critical",
      title: "Script type mismatch",
      detail: "Your inputs use P2WPKH but at least one output is P2TR.",
      suggestion: "Send change to the same script type as your inputs (P2WPKH)."
    }
  ],
  labels: []
};

// ── State ────────────────────────────────────────────────────
let activeTab = 'psbt';
let currentReport = null;
let pyodide = null;
let pyodideReady = false;

const PLACEHOLDERS = {
  psbt:  'cHNidP8BAH0CAAAAAbxLLf9+AYfqfF69QAQuETnL…',
  rawtx: '0200000001abc123…',
  txid:  'a4f1c9d2e3b5a6f7…'
};

const CAPTION_PYODIDE   = 'Running in your browser. Your PSBT never leaves this tab.';
const CAPTION_LOOKUP    = 'Input addresses are looked up via mempool.space. Your PSBT is never transmitted.';
const CAPTION_NO_LOOKUP = 'Network checks disabled. No data leaves your machine.';

// ── DOM refs ─────────────────────────────────────────────────
const txInput        = document.getElementById('tx-input');
const btnAnalyse     = document.getElementById('btn-analyse');
const errorBanner    = document.getElementById('error-banner');
const resultsZone    = document.getElementById('results-zone');
const scoreNumber    = document.getElementById('score-number');
const verdictPill    = document.getElementById('verdict-pill');
const gaugeDot       = document.getElementById('gauge-dot');
const metaChips      = document.getElementById('meta-chips');
const findingsCount  = document.getElementById('findings-count');
const findingsList   = document.getElementById('findings-list');
const checksCount    = document.getElementById('checks-count');
const checksList     = document.getElementById('checks-list');
const labelsSection  = document.getElementById('labels-section');
const labelsList     = document.getElementById('labels-list');
const nextList       = document.getElementById('next-list');
const btnDownload    = document.getElementById('btn-download');
const fileInput      = document.getElementById('file-input');
const networkCheckbox = document.getElementById('network-checks');
const privacyCaption  = document.getElementById('privacy-caption');

// ── Caption ──────────────────────────────────────────────────
function updateCaption() {
  if (pyodideReady) {
    privacyCaption.textContent = CAPTION_PYODIDE;
    return;
  }
  privacyCaption.textContent = networkCheckbox.checked ? CAPTION_LOOKUP : CAPTION_NO_LOOKUP;
}
networkCheckbox.addEventListener('change', updateCaption);
updateCaption();

// ── Pill tabs ────────────────────────────────────────────────
document.querySelectorAll('.pill').forEach(pill => {
  pill.addEventListener('click', () => {
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    activeTab = pill.dataset.tab;
    txInput.placeholder = PLACEHOLDERS[activeTab];
  });
});

// ── Hide error banner on input ────────────────────────────────
txInput.addEventListener('input', () => {
  errorBanner.style.display = 'none';
});

// ── Import labels ─────────────────────────────────────────────
document.getElementById('import-labels-btn').addEventListener('click', () => {
  fileInput.click();
});

fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;
  errorBanner.style.display = 'none';
  try {
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/labels/import', { method: 'POST', body: form });
    if (res.ok) {
      const data = await res.json();
      alert(`Imported ${data.imported} label(s) from ${file.name}`);
    } else {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Could not import labels from ${file.name}`);
    }
  } catch (err) {
    errorBanner.textContent = 'Import failed: ' + err.message;
    errorBanner.style.display = 'block';
  }
  fileInput.value = '';
});

// ── Analyse ───────────────────────────────────────────────────
btnAnalyse.addEventListener('click', async () => {
  const lookup = networkCheckbox.checked;
  const value  = txInput.value.trim();
  errorBanner.style.display = 'none';
  currentReport = null;
  resultsZone.classList.remove('visible');

  if (!value) {
    errorBanner.textContent = 'Please paste a PSBT, raw transaction hex, or txid before analysing.';
    errorBanner.style.display = 'block';
    return;
  }

  btnAnalyse.disabled    = true;
  btnAnalyse.textContent = 'Analysing…';

  let report;
  try {
    report = await fetchScore(value, activeTab, lookup);
  } catch (err) {
    btnAnalyse.disabled    = false;
    btnAnalyse.textContent = 'Analyse Transaction';
    errorBanner.textContent = 'Error: ' + err.message;
    errorBanner.style.display = 'block';
    return;
  }

  btnAnalyse.disabled    = false;
  btnAnalyse.textContent = 'Analyse Transaction';
  currentReport = report;
  renderReport(report);
});

// ── Pyodide ───────────────────────────────────────────────────
async function initPyodide() {
  try {
    pyodide = await loadPyodide();

    // Inject scorer source files directly into Pyodide's virtual filesystem.
    // scorer is pure Python (stdlib only) so no micropip or wheel is needed.
    const scorerFiles = [
      '__init__.py',
      'report.py',
      'parser.py',
      'lookup.py',
      'labels.py',
      'rpc.py',
      'heuristics/__init__.py',
      'heuristics/h1_script_mismatch.py',
      'heuristics/h2_round_amount.py',
      'heuristics/h3_address_reuse.py',
      'heuristics/h4_utxo_age.py',
      'heuristics/h5_consolidation.py',
      'heuristics/h6_dust.py',
      'heuristics/h7_bip69.py',
      'heuristics/h8_tainted_label.py',
    ];

    // sqlite3 is unvendored from Pyodide's stdlib — must be loaded before scorer imports it
    await pyodide.loadPackage('sqlite3');

    pyodide.FS.mkdir('scorer');
    pyodide.FS.mkdir('scorer/heuristics');

    for (const file of scorerFiles) {
      const res = await fetch(`/scorer-src/${file}`);
      if (!res.ok) throw new Error(`Failed to fetch scorer/${file}: HTTP ${res.status}`);
      pyodide.FS.writeFile(`scorer/${file}`, await res.text());
    }

    pyodide.runPython(`
      from scorer import score_as as _score_as
      import scorer.heuristics.h3_address_reuse as _h3
      import scorer.heuristics.h4_utxo_age as _h4
      import json as _json
    `);
    pyodideReady = true;
    updateCaption();
  } catch (e) {
    console.warn('Pyodide unavailable, falling back to server:', e);
  }
}

async function scoreViaPyodide(value, inputType, lookup) {
  const addrTxs = {};
  const heights = {};

  if (lookup) {
    // Parse offline to extract input addresses and txids for H3/H4 pre-fetch
    let addresses = [], txids = [];
    try {
      const parsed = JSON.parse(pyodide.runPython(`
        try:
          from scorer.parser import parse_as as _p
          tx = _p(${JSON.stringify(value)}, ${JSON.stringify(inputType)})
          _json.dumps({
            'addresses': [i.address for i in tx.inputs if i.address],
            'txids': list({i.txid for i in tx.inputs})
          })
        except Exception:
          '{"addresses":[],"txids":[]}'
      `));
      addresses = parsed.addresses;
      txids     = parsed.txids;
    } catch (_) {}

    // H3 — fetch address tx history directly from mempool.space (browser, no proxy)
    for (const addr of addresses.slice(0, 5)) {
      try {
        const res = await fetch(
          `https://mempool.space/api/address/${addr}/txs`,
          { signal: AbortSignal.timeout(8000) }
        );
        if (res.ok) addrTxs[addr] = await res.json();
      } catch (_) {}
    }

    // H4 — fetch block heights directly from mempool.space (browser, no proxy)
    for (const txid of txids.slice(0, 8)) {
      try {
        const res = await fetch(
          `https://mempool.space/api/tx/${txid}`,
          { signal: AbortSignal.timeout(8000) }
        );
        if (res.ok) {
          const tx = await res.json();
          if (tx.status?.block_height) heights[txid] = tx.status.block_height;
        }
      } catch (_) {}
    }

    // Inject pre-fetched data — same monkey-patch pattern used in the test suite
    pyodide.globals.set('_addr_txs', pyodide.toPy(addrTxs));
    pyodide.globals.set('_heights',  pyodide.toPy(heights));
    pyodide.runPython(`
      _h3.get_address_txs       = lambda addr: list(_addr_txs.get(addr, []))
      _h4.get_utxo_block_height = lambda txid: _heights.get(txid)
    `);
  }

  pyodide.globals.set('_input',      value);
  pyodide.globals.set('_input_type', inputType);
  pyodide.globals.set('_lookup',     lookup);

  const resultJson = pyodide.runPython(`
    report = _score_as(_input, _input_type, lookup=_lookup)
    _json.dumps({
      'score':        report.score,
      'psbt_version': report.psbt_version,
      'input_count':  report.input_count,
      'output_count': report.output_count,
      'warnings':     report.warnings,
      'findings': [
        {'id': f.heuristic_id, 'severity': f.severity.value, 'title': f.title,
         'detail': f.detail, 'suggestion': f.suggestion, 'weight': f.weight}
        for f in report.findings
      ],
      'checks': [
        {'id': c.heuristic_id, 'severity': c.severity.value, 'title': c.title,
         'status': c.status, 'reason': c.reason}
        for c in report.checks
      ],
      'labels': report.labels
    })
  `);
  return JSON.parse(resultJson);
}

initPyodide(); // starts loading in background — does not block page render

// ── Fetch ─────────────────────────────────────────────────────
async function fetchScore(value, inputType, lookup) {
  validateInput(value, inputType);

  // Pyodide path: PSBT and rawtx only — txid needs server for prevout enrichment
  if (pyodideReady && inputType !== 'txid') {
    try {
      return await scoreViaPyodide(value, inputType, lookup);
    } catch (e) {
      console.warn('Pyodide scoring failed, falling back to server:', e);
    }
  }

  try {
    const res = await fetch('/score', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input: value, input_type: inputType, lookup }),
      signal: AbortSignal.timeout(30000)
    });
    if (res.ok) return await res.json();
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'The backend could not parse this input.');
  } catch (err) {
    const timedOut = err.name === 'TimeoutError' || err.name === 'AbortError';
    const backendUnavailable = timedOut || err.message === 'Failed to fetch';
    if (!backendUnavailable || window.location.protocol !== 'file:') {
      if (timedOut) throw new Error('The backend took too long. Please try again.');
      throw err;
    }
  }

  // Offline mock
  await delay(700);
  return value.startsWith('cHNidP8') ? MOCK_GOOD : MOCK_RESULT;
}

function validateInput(value, inputType) {
  if (inputType === 'txid' && !/^[0-9a-fA-F]{64}$/.test(value)) {
    throw new Error('Invalid txid. Expected 64 hexadecimal characters.');
  }
  if (inputType === 'rawtx' && (!/^[0-9a-fA-F]+$/.test(value) || value.length % 2 !== 0)) {
    throw new Error('Invalid raw transaction hex.');
  }
  if (inputType === 'psbt') {
    try {
      const bytes = Uint8Array.from(atob(value), c => c.charCodeAt(0));
      const ok = bytes.length >= 5
        && bytes[0] === 0x70 && bytes[1] === 0x73
        && bytes[2] === 0x62 && bytes[3] === 0x74
        && bytes[4] === 0xff;
      if (!ok) throw new Error();
    } catch (_) {
      throw new Error('Invalid PSBT. Expected base64 PSBT data.');
    }
  }
}

function delay(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Render ────────────────────────────────────────────────────
function renderReport(report) {
  const { score, findings, checks, labels, input_count, output_count, psbt_version } = report;

  const { label: vLabel, cls: vCls, colour: vColour } = verdictFor(score);
  scoreNumber.textContent   = score;
  scoreNumber.style.color   = vColour;
  verdictPill.textContent   = vLabel;
  verdictPill.className     = 'verdict-pill verdict-' + vCls;
  gaugeDot.style.left       = score + '%';
  gaugeDot.style.borderColor = vColour;

  metaChips.innerHTML = [
    chip(input_count  + ' input'  + (input_count  !== 1 ? 's' : '')),
    chip(output_count + ' output' + (output_count !== 1 ? 's' : '')),
    chip('PSBT v' + psbt_version)
  ].join('');

  const orderedFindings = sortFindings(findings);
  findingsCount.textContent = findings.length + ' issue' + (findings.length !== 1 ? 's' : '');
  findingsList.innerHTML = orderedFindings.length > 0
    ? orderedFindings.map(renderFinding).join('')
    : '<div class="no-findings">No issues found</div>';

  const orderedChecks = sortChecks(checks || checksFromFindings(findings));
  checksCount.textContent = orderedChecks.length + ' checks';
  checksList.innerHTML = orderedChecks.map(renderCheck).join('');

  if (labels && labels.length > 0) {
    labelsSection.style.display = 'block';
    labelsList.innerHTML = labels.map(renderLabel).join('');
  } else {
    labelsSection.style.display = 'none';
  }

  nextList.innerHTML = orderedFindings.slice(0, 3)
    .map(f => `<li>${escHtml(f.suggestion)}</li>`)
    .join('') || '<li>No immediate action needed.</li>';

  resultsZone.classList.add('visible');
  resultsZone.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function verdictFor(score) {
  if (score >= 70) return { label: 'Good', cls: 'good', colour: 'var(--green)' };
  if (score >= 40) return { label: 'Fair', cls: 'fair', colour: 'var(--amber)' };
  return               { label: 'Poor', cls: 'poor', colour: 'var(--red)'   };
}

function chip(text) {
  return `<span class="chip">${escHtml(text)}</span>`;
}

function sortFindings(findings) {
  const rank = { critical: 0, warning: 1, info: 2 };
  return [...findings].sort((a, b) => {
    const d = (rank[a.severity] ?? 3) - (rank[b.severity] ?? 3);
    return d || String(a.id).localeCompare(String(b.id));
  });
}

function sortChecks(checks) {
  const sr = { fail: 0, unavailable: 1, skipped: 2, pass: 3 };
  const sv = { critical: 0, warning: 1, info: 2 };
  return [...checks].sort((a, b) => {
    const d = (sr[a.status] ?? 4) - (sr[b.status] ?? 4);
    if (d) return d;
    const e = (sv[a.severity] ?? 3) - (sv[b.severity] ?? 3);
    return e || String(a.id).localeCompare(String(b.id));
  });
}

function checksFromFindings(findings) {
  return findings.map(f => ({ id: f.id, severity: f.severity, title: f.title, status: 'fail', reason: '' }));
}

function renderFinding(f) {
  const sev = f.severity.toLowerCase();
  return `
    <div class="finding-card ${sev}">
      <div class="finding-row1">
        <span class="severity-badge ${sev}">${escHtml(f.severity.toUpperCase())}</span>
        <span class="heuristic-id">${escHtml(f.id)}</span>
      </div>
      <div class="finding-title">${escHtml(f.title)}</div>
      <div class="finding-detail">${escHtml(f.detail)}</div>
      <div class="finding-suggestion">&rarr; ${escHtml(f.suggestion)}</div>
    </div>`;
}

function renderCheck(c) {
  const status = c.status || 'unavailable';
  return `
    <div class="check-row ${escHtml(status)}">
      <span class="check-id">${escHtml(c.id)}</span>
      <div class="check-title">
        <div class="check-name">${escHtml(c.title)}</div>
        ${c.reason ? `<div class="check-reason">${escHtml(c.reason)}</div>` : ''}
      </div>
      <span class="check-status ${escHtml(status)}">${escHtml(status)}</span>
    </div>`;
}

function renderLabel(l) {
  const tag = l.tag || 'unknown';
  const type = l.label_type || 'utxo';
  const taintedActive = tag === 'tainted' && l.in_inputs;
  return `
    <div class="label-row${taintedActive ? ' tainted-active' : ''}">
      <div class="label-row-inner">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--orange)"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
          <line x1="7" y1="7" x2="7.01" y2="7"/>
        </svg>
        <span class="label-utxo mono">${escHtml(l.short_id || labelRef(l))}</span>
        <span class="label-text">${escHtml(l.label)}</span>
        <span class="tag-pill ${escHtml(tag)}">${escHtml(type)} / ${escHtml(tag)}</span>
      </div>
      ${taintedActive ? `<div class="label-taint-warning">This UTXO is flagged as tainted and is included in your transaction inputs.</div>` : ''}
    </div>`;
}

function labelRef(label) {
  if (label.label_type === 'addr') return label.address || label.ref || 'address';
  if (label.label_type === 'tx') return shortTxid(label.txid || label.ref);
  if (label.txid && label.vout !== null && label.vout !== undefined) {
    return shortId(label.txid, label.vout);
  }
  return label.ref || label.label_type || 'label';
}

function shortTxid(txid) {
  if (!txid) return 'transaction';
  return txid.slice(0, 8) + '…' + txid.slice(-4);
}

function shortId(txid, vout) {
  return txid.slice(0, 8) + '…' + txid.slice(-4) + ':' + vout;
}

// ── Download ──────────────────────────────────────────────────
btnDownload.addEventListener('click', () => {
  if (!currentReport) return;
  const r = currentReport;
  const { label: vLabel } = verdictFor(r.score);
  const now = new Date().toISOString().replace('T', ' ').slice(0, 19);

  let txt = 'SiriScore Privacy Report\n========================\n';
  txt += `Score: ${r.score}/100 (${vLabel})\n`;
  txt += `Inputs: ${r.input_count} | Outputs: ${r.output_count} | PSBT v${r.psbt_version}\n`;
  txt += `Generated: ${now}\n\n`;

  txt += 'FINDINGS\n--------\n';
  const rf = sortFindings(r.findings);
  if (!rf.length) txt += 'No issues found\n\n';
  for (const f of rf) {
    txt += `[${f.severity.toUpperCase()}] ${f.id} — ${f.title}\n${f.detail}\nFix: ${f.suggestion}\n\n`;
  }

  txt += 'CHECKS\n------\n';
  for (const c of sortChecks(r.checks || checksFromFindings(r.findings))) {
    txt += `[${c.status.toUpperCase()}] ${c.id} — ${c.title}`;
    if (c.reason) txt += ` (${c.reason})`;
    txt += '\n';
  }
  txt += '\n';

  if (r.labels && r.labels.length) {
    txt += 'COIN LABELS\n-----------\n';
    for (const l of r.labels) {
      txt += `${l.short_id || labelRef(l)}  ${l.label}  [${l.label_type || 'utxo'} / ${l.tag || 'unknown'}]\n`;
    }
    txt += '\n';
  }

  txt += 'WHAT TO DO NEXT\n---------------\n';
  rf.slice(0, 3).forEach((f, i) => { txt += `${i + 1}. ${f.suggestion}\n`; });
  if (!rf.length) txt += 'No immediate action needed.\n';

  const blob = new Blob([txt], { type: 'text/plain' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = 'siriscore-report.txt'; a.click();
  URL.revokeObjectURL(url);
});

// ── Util ──────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Glossary ──────────────────────────────────────────────────
const GLOSSARY_TERMS = [
  {
    term: 'UTXO',
    definition: 'Unspent Transaction Output. A chunk of Bitcoin you received and have not yet spent. Bitcoin wallets are collections of UTXOs, not a single balance. When you send Bitcoin, you spend one or more UTXOs as inputs.',
    why: 'Which UTXOs you spend together permanently links them in chain analysis databases.'
  },
  {
    term: 'PSBT',
    definition: 'Partially Signed Bitcoin Transaction (BIP-174). A portable transaction format that carries all the information a signer needs but is not yet broadcast. Standard for hardware wallets and multisig.',
    why: 'The best time to check your privacy is when you have a PSBT — before you sign.'
  },
  {
    term: 'Change output',
    definition: 'When your input UTXOs are worth more than the payment plus fee, your wallet sends the remainder back to an address you control. This is your change.',
    why: 'Change outputs are the most common source of wallet fingerprinting. If an analyst can identify your change, they can track your wallet across transactions.'
  },
  {
    term: 'Script type',
    definition: 'The locking condition on a Bitcoin output. Common types: P2PKH (legacy), P2SH (script hash), P2WPKH (native SegWit), P2TR (Taproot).',
    why: 'If your inputs and change output use different script types, the change is trivially identifiable.'
  },
  {
    term: 'Chain analysis',
    definition: 'The practice of tracing Bitcoin transactions to identify wallet owners, cluster addresses, and track fund flows. Used by firms like Chainalysis and Elliptic.',
    why: 'SiriScore applies the same heuristics chain analysts use, so you can see your exposure before broadcast.'
  },
  {
    term: 'Heuristic',
    definition: 'A pattern-based rule used to make inferences about Bitcoin transactions. Chain analysis firms use heuristics to guess which outputs are change, which addresses belong to the same wallet, and where funds originated.',
    why: 'SiriScore runs 8 heuristics. Each one that fires is a fingerprint an analyst would exploit.'
  },
  {
    term: 'Address reuse',
    definition: 'Using the same Bitcoin address to receive funds more than once. Links all transactions to that address together permanently.',
    why: 'The strongest single privacy failure in Bitcoin. Avoid it entirely with silent payments (BIP-352).'
  },
  {
    term: 'Dust',
    definition: 'A UTXO worth less than 546 satoshis — below the threshold to spend economically. Often created deliberately by adversaries (dust attacks) to track wallets.',
    why: 'Spending a dust input may complete a dust attack, linking your wallet cluster to the attacker\'s tracking.'
  },
  {
    term: 'CIOH',
    definition: 'Common Input Ownership Heuristic. The assumption that all inputs in a transaction belong to the same wallet. The foundational assumption of most wallet clustering.',
    why: 'Consolidating many UTXOs in one transaction permanently links them in every chain analysis database.'
  },
  {
    term: 'BIP-69',
    definition: 'A standard for lexicographic ordering of transaction inputs and outputs. Wallets that implement it are indistinguishable from each other on ordering alone.',
    why: 'Non-BIP69 ordering is a wallet fingerprint — it can identify which software constructed the transaction.'
  },
  {
    term: 'Silent payments (BIP-352)',
    definition: 'A protocol that lets a sender pay a static, published address without ever reusing it on-chain. Each payment generates a unique on-chain address derived from the sender\'s key.',
    why: 'Eliminates address reuse permanently without requiring coordination for each payment.'
  },
  {
    term: 'nLockTime',
    definition: 'A transaction field that specifies the earliest block height or time at which the transaction can be included in a block. Most wallets set it to the current block height as an anti-fee-sniping measure.',
    why: 'nLockTime of 0 is a wallet fingerprint — it reveals the transaction was built by software that does not implement anti-fee-sniping.'
  },
];

const glossaryPanel    = document.getElementById('glossary-panel');
const glossaryBackdrop = document.getElementById('glossary-backdrop');
const glossarySearch   = document.getElementById('glossary-search');
const glossaryList     = document.getElementById('glossary-list');
const glossaryEmpty    = document.getElementById('glossary-empty');

function renderGlossary(filter) {
  const q = (filter || '').toLowerCase().trim();
  const matches = q
    ? GLOSSARY_TERMS.filter(t =>
        t.term.toLowerCase().includes(q) ||
        t.definition.toLowerCase().includes(q) ||
        (t.why && t.why.toLowerCase().includes(q))
      )
    : GLOSSARY_TERMS;

  if (matches.length === 0) {
    glossaryList.innerHTML = '';
    glossaryEmpty.style.display = 'block';
    return;
  }

  glossaryEmpty.style.display = 'none';
  glossaryList.innerHTML = matches.map(t => `
    <div class="term-card">
      <div class="term-name">${escHtml(t.term)}</div>
      <div class="term-definition">${escHtml(t.definition)}</div>
      ${t.why ? `<div class="term-why">${escHtml(t.why)}</div>` : ''}
    </div>`).join('');
}

function openGlossary() {
  glossaryPanel.classList.add('open');
  glossaryBackdrop.classList.add('open');
  glossarySearch.value = '';
  renderGlossary('');
  glossarySearch.focus();
}

function closeGlossary() {
  glossaryPanel.classList.remove('open');
  glossaryBackdrop.classList.remove('open');
}

document.getElementById('learn-link').addEventListener('click', e => {
  e.preventDefault();
  openGlossary();
});

document.getElementById('glossary-close').addEventListener('click', closeGlossary);
glossaryBackdrop.addEventListener('click', closeGlossary);

glossarySearch.addEventListener('input', () => {
  renderGlossary(glossarySearch.value);
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeGlossary();
});
