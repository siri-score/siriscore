// ── Simple / Advanced mode preference ──────────────────────────
// Pure, DOM-free: no localStorage/window access in here so this module
// can be unit-tested directly under Node (see mode.test.mjs) and loaded
// as a plain <script> in the browser (see index.html / app.js).
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.SiriScoreMode = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {

  var MODE_KEY = 'siriscore-mode';
  var DEFAULT_MODE = 'simple';

  function normalizeMode(value) {
    return value === 'advanced' ? 'advanced' : DEFAULT_MODE;
  }

  // Plain-English copy per heuristic ID. Non-technical: no heuristic IDs,
  // no script-type/protocol jargon. One-sentence explanation + one-sentence fix.
  var PLAIN_FINDINGS = {
    H1: {
      emoji: '⚠️',
      title: 'Your change is identifiable',
      explain: 'The way this transaction is built makes it easy to tell which output is your change.',
      fix: 'Rebuild with matching address types.'
    },
    H2: {
      emoji: '⚠️',
      title: 'Your payment amount stands out',
      explain: 'Paying a suspiciously round amount makes it easy to guess which output is the payment and which is your change.',
      fix: 'Add a small random amount instead of a round number.'
    },
    H3: {
      emoji: '⚠️',
      title: "You're reusing an address",
      explain: 'One of the addresses you are spending from has been used before, linking this transaction to your past activity.',
      fix: 'Use a fresh address for every payment you receive.'
    },
    H4: {
      emoji: '⚠️',
      title: 'Your coins look linked together',
      explain: 'The coins you are spending were all received around the same time, which can reveal they belong to the same wallet.',
      fix: 'Mix coins from different time periods when you can.'
    },
    H5: {
      emoji: '⚠️',
      title: "You're combining a lot of coins",
      explain: 'Spending many coins together in one transaction makes it easy to prove they all belong to you.',
      fix: 'Avoid merging many coins at once, or use a coinjoin first.'
    },
    H6: {
      emoji: '⚠️',
      title: "You're spending a suspicious tiny amount",
      explain: "One of your coins is a tiny 'dust' amount, which is sometimes planted to track wallets.",
      fix: 'Leave dust inputs unspent, or clean them up with a coinjoin.'
    },
    H7: {
      emoji: 'ℹ️',
      title: 'Your wallet software is identifiable',
      explain: 'The order of the inputs and outputs reveals which wallet software built this transaction.',
      fix: 'Use a wallet that sorts inputs and outputs in the standard way.'
    },
    H8: {
      emoji: '⚠️',
      title: 'One of your coins is flagged',
      explain: 'A coin you are spending has been labelled as having a questionable history.',
      fix: "Review that coin's history before spending it with your other coins."
    },
    H9: {
      emoji: '✅',
      title: "You're spending mixed coins",
      explain: 'One of your coins already went through a coinjoin, which helps break the trail.',
      fix: 'No action needed — this is good for your privacy.'
    },
    H10: {
      emoji: '✅',
      title: 'This looks like a coinjoin',
      explain: 'This transaction matches the pattern of a coinjoin, one of the strongest privacy techniques available.',
      fix: 'No action needed — participating in a coinjoin protects your privacy.'
    },
    H11: {
      emoji: '✅',
      title: 'A more private option is available',
      explain: 'This payment could be sent as a Payjoin, which makes it much harder to identify your change.',
      fix: "Use your wallet's Payjoin support to send this payment."
    },
    H13: {
      emoji: 'ℹ️',
      title: 'Your wallet software is identifiable',
      explain: "The timing field on this transaction reveals it wasn't built with the standard anti-tracking setting.",
      fix: 'Use a wallet that sets this automatically.'
    },
    H14: {
      emoji: 'ℹ️',
      title: 'Your wallet software is identifiable',
      explain: 'Not all the coins in this transaction agree on whether it can be replaced with a higher fee, which is a wallet fingerprint.',
      fix: 'Use a wallet that applies the same fee-bump setting to every coin.'
    },
    H15: {
      emoji: 'ℹ️',
      title: 'Your fee looks distinctive',
      explain: 'Paying a suspiciously round fee rate can reveal which wallet software you used.',
      fix: 'Use a wallet with automatic, market-based fee estimation.'
    }
  };

  // A few heuristics (H14 today) can fire as either a problem or a
  // privacy-positive pass depending on the transaction — PLAIN_FINDINGS above
  // covers the problem case; this covers the positive case for those same
  // IDs so Simple mode never tells the user to "fix" something that already
  // passed. H9/H10/H11 are unconditionally positive so a single entry above
  // already covers them correctly.
  var PLAIN_FINDINGS_POSITIVE = {
    H14: {
      emoji: '✅',
      title: 'Your fee-bump signal is consistent',
      explain: 'Every coin in this transaction agrees on whether it can be replaced with a higher fee, so there is nothing unusual for a chain analyst to notice here.',
      fix: 'No action needed — this is already consistent.'
    }
  };

  function firstSentence(text) {
    if (!text) return '';
    var match = String(text).match(/^[^.!?]*[.!?]?/);
    return (match ? match[0] : String(text)).trim();
  }

  // Fallback for any heuristic not (yet) in PLAIN_FINDINGS above, so a new
  // heuristic added without updating this map degrades gracefully instead
  // of breaking Simple mode.
  function plainCopyFor(finding) {
    var id = finding && (finding.id || finding.heuristic_id);
    var isPositive = !!(finding && finding.positive);
    var known = id && ((isPositive && PLAIN_FINDINGS_POSITIVE[id]) || PLAIN_FINDINGS[id]);
    if (known) return known;

    var severity = (finding && finding.severity || '').toLowerCase();
    var emoji = finding && finding.positive ? '✅' : (severity === 'info' ? 'ℹ️' : '⚠️');
    return {
      emoji: emoji,
      title: (finding && finding.title) || 'Privacy finding',
      explain: firstSentence(finding && finding.detail) || 'This transaction has a privacy-relevant property.',
      fix: firstSentence(finding && finding.suggestion) || 'Review this before broadcasting.'
    };
  }

  return {
    MODE_KEY: MODE_KEY,
    DEFAULT_MODE: DEFAULT_MODE,
    normalizeMode: normalizeMode,
    PLAIN_FINDINGS: PLAIN_FINDINGS,
    PLAIN_FINDINGS_POSITIVE: PLAIN_FINDINGS_POSITIVE,
    plainCopyFor: plainCopyFor
  };
});
