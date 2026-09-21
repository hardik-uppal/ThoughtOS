import test from 'node:test';
import assert from 'node:assert/strict';
import { freshNotes, validateNotes, filtered, related, topicsCloud, addLink, removeLink, suggestions } from '../public/model.js';

test('20 independent valid sample notes; links point to existing notes', () => {
  const notes = freshNotes();
  assert.equal(notes.length, 20);
  assert.ok(validateNotes(notes));
  notes[0].links.push('bad');
  assert.ok(!validateNotes(notes));
  assert.ok(validateNotes(freshNotes()));
});
test('search is case-insensitive and combines with topic/tag filters', () => {
  const notes = freshNotes();
  assert.equal(filtered(notes, { topic: 'Wardrub' }).length, 4);
  assert.deepEqual(filtered(notes, { query: 'DIFFUSION' }).map(n => n.id), ['n8']);
  assert.equal(filtered(notes, { topic: 'Wardrub', tag: 'experiments' }).length, 1);
  assert.equal(filtered(notes, { query: 'not-existing' }).length, 0);
});
test('links work in both directions without duplicates or self-links', () => {
  const notes = freshNotes();
  assert.ok(related(notes, 'n2').some(n => n.id === 'n1'));
  const linked = addLink(notes, 'n1', 'n20');
  assert.ok(related(linked, 'n20').some(n => n.id === 'n1'));
  assert.equal(addLink(linked, 'n20', 'n1'), linked);
  assert.equal(addLink(notes, 'n1', 'n1'), notes);
  assert.equal(addLink(notes, 'n1', 'unknown'), notes);
  const removed = removeLink(linked, 'n20', 'n1');
  assert.ok(!related(removed, 'n1').some(n => n.id === 'n20'));
  assert.ok(!notes[0].links.includes('n20'));
});
test('cloud frequency counts notes, not duplicated tags', () => {
  const notes = freshNotes();
  const count = topicsCloud(notes).find(([tag]) => tag === 'thoughtos')[1];
  notes[0].tags.push('thoughtos');
  assert.equal(topicsCloud(notes).find(([tag]) => tag === 'thoughtos')[1], count);
});
test('tag suggestions exclude existing links and do not modify the graph', () => {
  const notes = freshNotes(), before = JSON.stringify(notes);
  const items = suggestions(notes, 'n1');
  assert.ok(items.length > 0);
  assert.ok(items.every(({ note, tags }) => note.id !== 'n1' && tags.length > 0 && !related(notes, 'n1').some(n => n.id === note.id)));
  assert.equal(JSON.stringify(notes), before);
  assert.deepEqual(suggestions(notes, 'missing'), []);
});
test('bad storage data fails validation', () => {
  for (const value of [null, {}, [], [null], [{ id: 'a' }]]) assert.equal(validateNotes(value), false);
  const notes = freshNotes();
  notes[0].title = '';
  assert.equal(validateNotes(notes), false);
});

import { migrateNotes, validateGraph, edges, describeLink, renameLink, deriveMetadata, semanticMatches, normalisePrefs } from '../public/model.js';
test('legacy links migrate once, unnamed, with original note text preserved', () => {
  const old = freshNotes(); old[1].links.push('n1'); const copy = structuredClone(old);
  const notes = migrateNotes(old);
  assert.ok(validateGraph(notes)); assert.deepEqual(old, copy);
  assert.equal(edges(notes).filter(e => e.source === 'n1' && e.target === 'n2').length, 1);
  assert.ok(edges(notes).every(e => !e.label && !e.directed));
  assert.equal(notes[0].body, old[0].body); assert.deepEqual(migrateNotes(notes), notes);
});
test('named edges preserve direction, rename from either end, reject duplicate records', () => {
  let notes = addLink(migrateNotes(freshNotes()), 'n1', 'n20', 'inspires', true);
  assert.equal(describeLink(notes, 'n1', 'n20'), '→ inspires');
  assert.equal(describeLink(notes, 'n20', 'n1'), '← inspires');
  notes = renameLink(notes, 'n20', 'n1', 'challenges', true);
  assert.equal(describeLink(notes, 'n1', 'n20'), '→ challenges');
  assert.ok(validateGraph(notes));
  notes[19].connections.push({ target: 'n1', label: 'contradiction', directed: true });
  assert.equal(validateGraph(notes), false);
});
test('tag syntax is exact and multiple constraints combine, including semantic matches', () => {
  const notes = freshNotes();
  assert.equal(filtered(notes, { query: '#thoughtos tag:discovery' }).length, 2);
  assert.equal(filtered(notes, { query: '#thought' }).length, 0);
  const vectors = Object.fromEntries(notes.map(n => [n.id, [1, 0]]));
  const result = semanticMatches(notes, vectors, [1, 0], { query: 'forgotten idea #thoughtos tag:discovery', topic: 'Learning' });
  assert.deepEqual(result.map(r => r.note.id), ['n19']);
  assert.deepEqual(semanticMatches(notes, vectors, [0, 1], {}), []);
});
test('capture metadata is deterministic and preferences never opt into model/recording', () => {
  const body = '  # A rough thought\n\n experiments experiments\n  ';
  const meta = deriveMetadata(body, freshNotes());
  assert.equal(meta.title, 'A rough thought'); assert.ok(meta.tags.includes('experiments'));
  assert.equal(normalisePrefs().semantic, false); assert.equal(normalisePrefs().record, false);
});

import { collectionNames, normaliseCollection, surroundingNotes } from '../public/model.js';
test('collections grow from assigned notes with normalised names and an unsorted default', () => {
  const notes = freshNotes();
  assert.equal(normaliseCollection('  Wardrub  ', notes), 'Wardrub');
  assert.equal(normaliseCollection('wardrub', notes), 'Wardrub');
  assert.equal(normaliseCollection('', notes), 'Unsorted');
  notes[0].topic = normaliseCollection('  Writing   practice ', notes);
  assert.ok(validateGraph(notes)); assert.ok(collectionNames(notes).includes('Writing practice'));
  assert.equal(filtered(notes, { topic: 'Writing practice' }).length, 1);
  notes[0].topic = 'Everyday'; assert.ok(!collectionNames(notes).includes('Writing practice'));
});
test('the neighborhood includes every unconnected note, including those with no shared tags', () => {
  const notes = freshNotes(), before = JSON.stringify(notes);
  const all = surroundingNotes(notes, 'n3'), unlinked = surroundingNotes(notes, 'n3', { scope: 'unlinked' });
  assert.equal(all.length, 19); assert.equal(new Set(all.map(x => x.note.id)).size, 19);
  assert.equal(all[0].linked, false); assert.equal(all[1].linked, true);
  assert.equal(unlinked.length, 14); assert.ok(unlinked.some(n => !n.tags.length));
  assert.ok(unlinked.every(n => !n.linked)); assert.equal(JSON.stringify(notes), before);
  assert.equal(surroundingNotes(notes, 'n3', { scope: 'linked' }).length, 5);
});
