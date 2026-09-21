import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const url = process.env.PROTOTYPE_URL || 'http://127.0.0.1:4323';
const key = 'thoughtos.visual-garden.v1', snapshotsKey = 'thoughtos.visual-garden.experiments.v1';
const errors = [];
try {
  const context = await browser.newContext({ viewport: { width: 1512, height: 1000 }, reducedMotion: 'reduce' });
  const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
  await page.goto(url);
  const utility = async id => {
    if (!await page.locator(`#${id}`).isVisible()) {
      if (['source-info','reset'].includes(id)) await page.locator('#toggle-sidebar').click();
      else await page.locator('#desk-menu > summary').click();
    }
    await page.locator(`#${id}`).click();
  };
  const data = () => page.evaluate(k => JSON.parse(localStorage.getItem(k)), key);
  // Reader on demand and denser cards.
  assert.equal(await page.locator('#inspector').isVisible(), false);
  const columns = await page.locator('.desk-grid').evaluate(e => getComputedStyle(e).gridTemplateColumns.split(' ').length);
  assert.ok(columns >= 4);
  await page.locator('[data-open="n1"]').click();
  assert.equal(await page.locator('#inspector').isVisible(), true);
  await page.keyboard.press('Escape'); assert.equal(await page.locator('#inspector').isVisible(), false);
  // A freeform capture preserves whitespace; suggestions only apply when accepted.
  await page.keyboard.press('n');
  assert.equal(await page.locator('[name="body"]').evaluate(e => e === document.activeElement), true);
  const raw = '  # A question about experiments\n\n  experiments need baselines.  \n';
  await page.locator('[name="body"]').fill(raw);
  await page.locator('[data-metadata-tag="experiments"]').click();
  await page.locator('#suggest-title').click();
  await page.screenshot({ path: '/tmp/thoughtos-capture-v3.png' });
  await page.keyboard.press('Meta+s');
  const capture = (await data()).notes.at(-1);
  assert.equal(capture.body, raw); assert.equal(capture.title, 'A question about experiments'); assert.deepEqual(capture.tags, ['experiments']);
  assert.equal(await page.evaluate(k => localStorage.getItem(k), snapshotsKey), null, 'Recording defaults off');
  await page.locator('#close-reader').click();
  // Structured mode persists as a preference, but typing never triggers shortcuts.
  await page.keyboard.press('n'); await page.locator('#compose-mode').selectOption('structured');
  await page.locator('[name="title"]').fill('Structured sample'); await page.locator('[name="body"]').fill('f n e c');
  await page.keyboard.press('Control+s'); await page.reload();
  await page.locator('#new-note').click(); assert.equal(await page.locator('#compose-mode').inputValue(), 'structured'); await page.keyboard.press('Escape');
  // Named directional connection, edited from the reverse side, reload-safe.
  await page.locator('.note-card [data-connect="n1"]').click();
  await page.locator('#link-label').fill('inspires'); await page.locator('#link-directed').check();
  await page.locator('#picker-search').fill('Leave a trail'); await page.locator('[data-pick="n20"]').click();
  assert.match(await page.locator('#inspector [data-hop="n20"]').textContent(), /→ inspires/);
  await page.locator('#inspector [data-hop="n20"]').click(); await page.locator('[data-read]').click();
  assert.match(await page.locator('#inspector [data-hop="n1"]').textContent(), /← inspires/);
  await page.locator('[data-name-link="n1"]').click();
  await page.locator('#relationship-label').fill('provides a starting point for'); await page.locator('#relationship-form .capture-button').click();
  assert.match(await page.locator('#inspector [data-hop="n1"]').textContent(), /← provides a starting point for/);
  await page.reload();
  const named = (await data()).notes.find(n => n.id === 'n1').connections.find(e => e.target === 'n20');
  assert.deepEqual(named, { target: 'n20', label: 'provides a starting point for', directed: true });
  // Named snapshots, completed-action recording, restore, safety restore, deletion.
  await utility('experiments'); await page.locator('#snapshot-title').fill('Good baseline'); await page.locator('#snapshot-form button').click();
  assert.equal(await page.locator('.snapshot-row').count(), 1);
  await page.keyboard.press('Escape'); await utility('settings'); await page.locator('#record-pref').check(); await page.keyboard.press('Escape');
  await page.locator('.note-card [data-edit="n1"]').click(); await page.locator('[name="title"]').fill('Changed while recording'); await page.keyboard.press('Meta+s');
  await utility('experiments'); assert.equal(await page.locator('.snapshot-row').count(), 2);
  const baseline = page.locator('.snapshot-row').filter({ has: page.getByText('Good baseline', { exact: true }) });
  page.once('dialog', d => d.accept()); await baseline.locator('[data-snapshot-restore]').click();
  assert.equal((await data()).notes[0].title, 'A place to wander');
  const safety = page.locator('.snapshot-row').filter({ has: page.getByText('Before restoring Good baseline', { exact: true }) });
  page.once('dialog', d => d.accept()); await safety.locator('[data-snapshot-restore]').click();
  assert.equal((await data()).notes[0].title, 'Changed while recording');
  page.once('dialog', d => d.accept()); await baseline.locator('[data-snapshot-delete]').click(); assert.equal(await baseline.count(), 0);
  await page.screenshot({ path: '/tmp/thoughtos-snapshots-v3.png' });
  await page.keyboard.press('Escape');
  // If the recovery copy cannot be stored, restoration must not mutate notes.
  const beforeFailedRestore = await data();
  await utility('experiments');
  await page.evaluate(() => { window.realSetItem = Storage.prototype.setItem; Storage.prototype.setItem = function() { throw new DOMException('Quota exceeded', 'QuotaExceededError'); }; });
  page.once('dialog', d => d.accept()); await page.locator('[data-snapshot-restore]').first().click();
  assert.match(await page.locator('#snapshot-status').textContent(), /Could not/);
  assert.deepEqual(await data(), beforeFailedRestore);
  await page.evaluate(() => { Storage.prototype.setItem = window.realSetItem; });
  await page.keyboard.press('Escape');
  // Corrupt snapshot storage is preserved and does not replace current notes.
  const before = await data();
  await page.evaluate(k => localStorage.setItem(k, '{bad json'), snapshotsKey);
  await utility('experiments'); assert.match(await page.locator('#snapshot-status').textContent(), /Could not/);
  await page.locator('#snapshot-title').fill('Do not overwrite'); await page.locator('#snapshot-form button').click();
  assert.equal(await page.evaluate(k => localStorage.getItem(k), snapshotsKey), '{bad json'); assert.deepEqual(await data(), before);
  await page.keyboard.press('Escape');
  // Actual local embeddings, hard tag filters, and separately labelled inferred matches.
  await page.locator('#find-note').click(); await page.locator('#meaning-search').check(); await page.locator('#picker-search').fill('clothing photographs #wardrub');
  await page.waitForFunction(() => document.querySelector('#meaning-status').textContent === 'Local meaning + text & tags', null, { timeout: 60000 });
  assert.ok(await page.locator('[data-pick]').count() > 0);
  const ids = await page.locator('[data-pick]').evaluateAll(es => es.map(e => e.dataset.pick));
  const saved = await data(); assert.ok(ids.every(id => saved.notes.find(n => n.id === id).tags.includes('wardrub')));
  assert.match(await page.locator('#picker-results').textContent(), /Similar meaning/);
  await page.screenshot({ path: '/tmp/thoughtos-meaning-v3.png' });
  await page.locator('[data-pick]').first().click();
  assert.match(await page.locator('.around-grid').textContent(), /similar meaning/);
  // Model failure is explicit and falls back to normal search without false semantic labels.
  await page.route('**/api/semantic', route => route.fulfill({ json: { error: 'Local model unavailable. Text & tags still work.' } }));
  await page.locator('#find-note').click(); await page.locator('#picker-search').fill('diffusion');
  await page.waitForFunction(() => document.querySelector('#meaning-status').textContent.includes('unavailable'));
  assert.equal(await page.locator('[data-pick="n8"]').count(), 1);
  assert.doesNotMatch(await page.locator('#picker-results').textContent(), /Similar meaning/);
  await page.keyboard.press('Escape'); await page.unroute('**/api/semantic');
  // Semantic requests are rejected from other origins and cannot expose local files.
  const headers = { Origin: 'https://untrusted.example', 'Content-Type': 'application/json' };
  assert.equal((await context.request.post(url + '/api/semantic', { headers, data: { texts: ['test'] } })).status(), 403);
  assert.equal((await context.request.post(url + '/api/semantic', { headers: { ...headers, Origin: url, Host: 'untrusted.example' }, data: { texts: ['test'] } })).status(), 403);
  assert.equal((await context.request.get(url + '/experiments.sqlite3')).status(), 404);
  assert.equal((await context.request.post(url + '/api/snapshots')).status(), 405);
  // Small-screen controls stay usable with the reader and dialogs on demand.
  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const mobile = await mobileContext.newPage(); mobile.on('pageerror', e => errors.push(e.message)); await mobile.goto(url);
  const noOverflow = () => mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
  assert.ok(await noOverflow());
  await mobile.locator('[data-open="n1"]').click(); assert.equal(await mobile.locator('#inspector').isVisible(), true); assert.ok(await noOverflow());
  await mobile.locator('#close-reader').click(); await mobile.locator('#new-note').click();
  await mobile.locator('[name="body"]').fill('A short mobile capture'); assert.ok(await noOverflow());
  await mobile.screenshot({ path: '/tmp/thoughtos-mobile-capture-v3.png' });
  await mobile.locator('[data-close="editor-dialog"]').click();
  await mobile.locator('#desk-menu > summary').click(); await mobile.locator('#experiments').click(); await mobile.locator('#snapshot-title').fill('Mobile baseline'); await mobile.locator('#snapshot-form button').click();
  assert.ok(await noOverflow()); await mobile.screenshot({ path: '/tmp/thoughtos-mobile-snapshots-v3.png' });
  await mobile.locator('[data-close="experiments-dialog"]').click();
  await mobile.setViewportSize({ width: 768, height: 1024 }); assert.ok(await noOverflow());
  await mobileContext.close();
  // Invalid saved graph blocks migration instead of silently dropping links.
  const legacyContext = await browser.newContext(); const legacyPage = await legacyContext.newPage(); await legacyPage.goto(url);
  await legacyPage.evaluate(async k => { const { freshNotes } = await import('/model.js'); localStorage.setItem(k, JSON.stringify({ version: 1, notes: freshNotes() })); }, key);
  const legacyText = await legacyPage.evaluate(k => localStorage.getItem(k), key);
  await legacyPage.reload(); await legacyPage.locator('.note-card [data-edit="n1"]').click(); await legacyPage.locator('[name="body"]').fill('Migrated text'); await legacyPage.keyboard.press('Meta+s');
  assert.equal(await legacyPage.evaluate(k => localStorage.getItem(k + '.pre-v3'), key), legacyText);
  assert.equal(await legacyPage.evaluate(k => JSON.parse(localStorage.getItem(k)).version, key), 2);
  assert.deepEqual(errors, []);
  console.log('PASS: iteration 03 reader, density, capture, named edges, snapshots/restore, recording, actual local semantic search, tag constraints, migration and API isolation');
} finally { await browser.close(); }
