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
