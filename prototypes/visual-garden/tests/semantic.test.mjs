import test from 'node:test';
import assert from 'node:assert/strict';
import { embed } from '../semantic.mjs';
test('embedding request stays on loopback, uses fixed model and CPU option', async () => {
  const vectors = await embed(['search_query: clothing'], async (url, opts) => {
    assert.equal(url, 'http://127.0.0.1:11434/api/embed');
    const body = JSON.parse(opts.body); assert.equal(body.model, 'nomic-embed-text'); assert.equal(body.options.num_gpu, 0);
    return { ok: true, json: async () => ({ embeddings: [[.1, .2]] }) };
  }); assert.deepEqual(vectors, [[.1, .2]]);
});
test('embedding limits and malformed upstream data fail closed', async () => {
  for (const value of [[], [null], Array(33).fill('x'), ['x'.repeat(21001)]]) await assert.rejects(embed(value), /Invalid/);
  await assert.rejects(embed(['a'], async () => ({ ok: true, json: async () => ({ embeddings: [[null]] }) })), /Invalid/);
  await assert.rejects(embed(['a'], async () => ({ ok: false })), /unavailable/);
});
