// Run with: node --test web/mode.test.mjs
// Covers the pure Simple/Advanced preference logic in mode.js. DOM/localStorage
// wiring in app.js and the actual header toggle are verified manually in a
// browser — there's no jsdom/browser test harness in this repo (Python/pytest
// only) and adding one for a single feature would be disproportionate.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const SiriScoreMode = require('./mode.js');

test('MODE_KEY and DEFAULT_MODE are stable, expected values', () => {
  assert.equal(SiriScoreMode.MODE_KEY, 'siriscore-mode');
  assert.equal(SiriScoreMode.DEFAULT_MODE, 'simple');
});

test('normalizeMode defaults to simple for anything but the literal string "advanced"', () => {
  assert.equal(SiriScoreMode.normalizeMode('advanced'), 'advanced');
  assert.equal(SiriScoreMode.normalizeMode('simple'), 'simple');
  assert.equal(SiriScoreMode.normalizeMode(undefined), 'simple');
  assert.equal(SiriScoreMode.normalizeMode(null), 'simple');
  assert.equal(SiriScoreMode.normalizeMode(''), 'simple');
  assert.equal(SiriScoreMode.normalizeMode('Advanced'), 'simple');
  assert.equal(SiriScoreMode.normalizeMode('garbage'), 'simple');
});

test('plainCopyFor covers every currently-shipped heuristic with non-technical copy', () => {
  const knownIds = ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10', 'H11', 'H13', 'H14', 'H15'];
  for (const id of knownIds) {
    const copy = SiriScoreMode.plainCopyFor({ id, severity: 'warning', title: 't', detail: 'd', suggestion: 's' });
    assert.ok(copy.emoji, `${id} should have an emoji`);
    assert.ok(copy.title.length > 0, `${id} should have a plain title`);
    assert.ok(copy.explain.length > 0, `${id} should have a plain explanation`);
    assert.ok(copy.fix.length > 0, `${id} should have a plain fix`);
    // Non-technical: no bare heuristic IDs leaking into the plain copy.
    assert.doesNotMatch(copy.title, /\bH\d+\b/);
    assert.doesNotMatch(copy.explain, /\bH\d+\b/);
  }
});

test('plainCopyFor matches the issue example for H1', () => {
  const copy = SiriScoreMode.plainCopyFor({ id: 'H1', severity: 'critical' });
  assert.equal(copy.title, 'Your change is identifiable');
  assert.match(copy.explain, /easy to tell which output is your change/);
  assert.match(copy.fix, /matching address types/);
});

test('plainCopyFor falls back gracefully for an unknown/future heuristic id', () => {
  const copy = SiriScoreMode.plainCopyFor({
    id: 'H99',
    severity: 'warning',
    title: 'Some new heuristic',
    detail: 'Technical detail sentence one. Technical detail sentence two.',
    suggestion: 'Do the technical fix. And then some more detail.'
  });
  assert.equal(copy.emoji, '⚠️');
  assert.equal(copy.title, 'Some new heuristic');
  assert.equal(copy.explain, 'Technical detail sentence one.');
  assert.equal(copy.fix, 'Do the technical fix.');
});

test('plainCopyFor uses the positive-branch copy for a heuristic that can fire both ways (H14)', () => {
  // H14 (RBF signalling) is a WARNING when inputs disagree, but INFO/positive
  // when they agree — Simple mode must not tell the user to "fix" a pass.
  const negative = SiriScoreMode.plainCopyFor({ id: 'H14', severity: 'warning', positive: false });
  assert.equal(negative.emoji, 'ℹ️');
  assert.match(negative.fix, /same fee-bump setting/);

  const positive = SiriScoreMode.plainCopyFor({ id: 'H14', severity: 'info', positive: true });
  assert.equal(positive.emoji, '✅');
  assert.match(positive.fix, /No action needed/);
  assert.notEqual(positive.fix, negative.fix);
});

test('plainCopyFor falls back for a positive/info finding with no detail at all', () => {
  const copy = SiriScoreMode.plainCopyFor({ id: 'H99', severity: 'info', positive: true });
  assert.equal(copy.emoji, '✅');
  assert.equal(copy.title, 'Privacy finding');
  assert.ok(copy.explain.length > 0);
  assert.ok(copy.fix.length > 0);
});
