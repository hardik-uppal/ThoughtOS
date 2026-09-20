import http from 'node:http';
import { readFile } from 'node:fs/promises';

// Deliberately serve only these public assets. Never expose the repo, DB or credentials.
const files = new Map([
  ['/', ['index.html', 'text/html']],
  ['/index.html', ['index.html', 'text/html']],
  ['/style.css', ['style.css', 'text/css']],
  ['/desk.css', ['desk.css', 'text/css']],
  ['/app.js', ['app.js', 'text/javascript']],
  ['/model.js', ['model.js', 'text/javascript']],
  ['/icon.svg', ['icon.svg', 'image/svg+xml']],
]);
const port = Number(process.env.PORT || 4321);
const host = process.env.HOST || '127.0.0.1';
http.createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'");
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
