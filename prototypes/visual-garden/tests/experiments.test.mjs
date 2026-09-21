import test from 'node:test';
import assert from 'node:assert/strict';
import { saveExperiment, readExperiments, deleteExperiment, EXPERIMENT_KEY } from '../public/experiments.js';
import { freshNotes, migrateNotes, normalisePrefs } from '../public/model.js';
const storage = () => { const map = new Map(); return { getItem: k => map.get(k) ?? null, setItem: (k,v) => map.set(k,v) }; };
const input = () => ({ title: 'Before experimenting', notes: migrateNotes(freshNotes()), prefs: normalisePrefs() });
test('snapshots copy complete graph and preserve named snapshots through retention', () => {
  const store = storage(), source = input(); const first = saveExperiment(store, source);
  source.notes[0].body = 'changed';
  assert.notEqual(readExperiments(store)[0].payload.notes[0].body, 'changed');
  for (let i = 0; i < 25; i++) saveExperiment(store, { ...input(), kind: 'auto' });
  for (let i = 0; i < 25; i++) saveExperiment(store, { ...input(), kind: 'safety' });
  const rows = readExperiments(store);
  assert.equal(rows.length, 41); assert.ok(rows.some(s => s.id === first.id));
  deleteExperiment(store, first.id); assert.equal(readExperiments(store).length, 40);
});
test('corrupt storage and failed writes preserve existing snapshots', () => {
  const store = storage(); store.setItem(EXPERIMENT_KEY, '{bad');
  assert.throws(() => saveExperiment(store, input()));
  assert.equal(store.getItem(EXPERIMENT_KEY), '{bad');
  const good = storage(); saveExperiment(good, input()); const before = good.getItem(EXPERIMENT_KEY);
  good.setItem = () => { throw new Error('Quota exceeded'); };
  assert.throws(() => saveExperiment(good, input()), /Quota/);
  assert.equal(good.getItem(EXPERIMENT_KEY), before);
});
test('manual cap fails without deleting older records, malformed graph rejected', () => {
  const store = storage(); for (let i = 0; i < 50; i++) saveExperiment(store, input());
  assert.throws(() => saveExperiment(store, input()), /50 named/);
  assert.equal(readExperiments(store).length, 50);
  const bad = input(); bad.notes[0].connections[0].target = 'missing';
  assert.throws(() => saveExperiment(storage(), bad), /Invalid snapshot/);
});
