// Fixed loopback endpoint: browser requests cannot choose an upstream URL or model.
export async function embed(texts, fetcher = fetch) {
  if (!Array.isArray(texts) || !texts.length || texts.length > 32 || texts.some(t => typeof t !== 'string' || t.length > 21000)) throw new Error('Invalid embedding input');
  const response = await fetcher('http://127.0.0.1:11434/api/embed', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'nomic-embed-text', input: texts, truncate: true, options: { num_gpu: 0 } }),
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error('Local embedding model unavailable');
  const { embeddings } = await response.json();
  if (!Array.isArray(embeddings) || embeddings.length !== texts.length || !embeddings.every(v => Array.isArray(v) && v.length > 0 && v.length <= 4096 && v.length === embeddings[0].length && v.every(Number.isFinite))) throw new Error('Invalid embedding response');
  return embeddings;
}
