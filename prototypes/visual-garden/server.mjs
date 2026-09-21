import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { embed } from './semantic.mjs';

// Deliberately serve only these public assets. Never expose the repo, DB or credentials.
const files = new Map([
  ['/', ['index.html', 'text/html']],
  ['/index.html', ['index.html', 'text/html']],
  ['/style.css', ['style.css', 'text/css']],
  ['/desk.css', ['desk.css', 'text/css']],
  ['/app.js', ['app.js', 'text/javascript']],
  ['/model.js', ['model.js', 'text/javascript']],
  ['/experiments.js', ['experiments.js', 'text/javascript']],
  ['/icon.svg', ['icon.svg', 'image/svg+xml']],
]);
const port = Number(process.env.PORT || 4321);
const host = process.env.HOST || '127.0.0.1';
let semanticBusy = false;
http.createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'");
  // Validate Host as well as Origin to reject DNS rebinding and cross-site inference requests.
  const authority = `${host.includes(':') ? `[${host}]` : host}:${port}`;
  if (req.headers.host !== authority && !(host === '127.0.0.1' && req.headers.host === `localhost:${port}`)) { res.writeHead(403); res.end('Invalid host'); return; }
  if (req.url === '/api/semantic') {
    res.setHeader('Content-Type', 'application/json');
    if (req.method !== 'POST') { res.writeHead(405); res.end('{}'); return; }
    if (req.headers.origin !== `http://${req.headers.host}` || req.headers['content-type'] !== 'application/json') { res.writeHead(403); res.end('{}'); return; }
    if (process.env.ENABLE_SEMANTIC !== '1') { res.writeHead(200); res.end(JSON.stringify({ error: 'Local meaning search is not enabled on this server. Text and tag search remain available.' })); return; }
    if (semanticBusy) { res.writeHead(200); res.end(JSON.stringify({ error: 'Local model is busy. Try again shortly.' })); return; }
    semanticBusy = true;
    try {
      let size = 0, chunks = [];
      for await (const chunk of req) { size += chunk.length; if (size > 750000) { res.writeHead(413); res.end('{}'); return; } chunks.push(chunk); }
      const { texts } = JSON.parse(Buffer.concat(chunks).toString());
      res.end(JSON.stringify({ embeddings: await embed(texts) }));
    } catch { res.end(JSON.stringify({ error: 'Local model unavailable or invalid request. Text and tag search remain available.' })); }
    finally { semanticBusy = false; }
    return;
  }
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405, { Allow: 'GET, HEAD' }); res.end('Read-only prototype'); return; }
  let pathname;
  try { pathname = new URL(req.url, 'http://localhost').pathname; }
  catch { res.writeHead(400); res.end('Bad request'); return; }
  const file = files.get(pathname);
  if (!file) { res.writeHead(404); res.end('Not found'); return; }
  try {
    const content = await readFile(new URL(`./public/${file[0]}`, import.meta.url));
    res.writeHead(200, { 'Content-Type': `${file[1]}; charset=utf-8` });
    res.end(req.method === 'HEAD' ? undefined : content);
  } catch { res.writeHead(500); res.end('Unable to load prototype asset'); }
}).listen(port, host, () => console.log(`ThoughtOS visual prototype: http://${host}:${port} (sample data only)`));
