import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const url = process.env.PROTOTYPE_URL || 'http://127.0.0.1:4323';
try {
  const context = await browser.newContext({ viewport: { width: 1203, height: 781 }, reducedMotion: 'reduce' });
  const page = await context.newPage(), errors = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto(url);
  assert.equal(await page.locator('#sidebar').isVisible(), false);
  assert.ok((await page.locator('.note-card').first().boundingBox()).y < 100, 'Notes start immediately below the toolbar');
  // The full neighborhood is visible with unconnected notes above the fold.
  await page.locator('[data-explore="n3"]').first().click();
  assert.equal(await page.locator('.around-card').count(), 19);
  assert.equal(await page.locator('.nearby-card').count(), 14);
  assert.equal(await page.locator('.branch-card').count(), 5);
  const board = await page.locator('.orbit-layout').boundingBox(), focus = await page.locator('.chain-focus').boundingBox();
  assert.ok(Math.abs(focus.x + focus.width/2 - (board.x + board.width/2)) < 2, 'Current thought is centered');
  const left = await page.locator('.orbit-left').boundingBox(), right = await page.locator('.orbit-right').boundingBox();
  assert.ok(left.x + left.width < focus.x && right.x > focus.x + focus.width, 'Other notes surround both sides');
  assert.ok(await page.locator('.is-linked.tone-tags').count() > 0);
  assert.ok(await page.locator('.nearby-card.tone-other').count() > 0);

  const firstUnlinked = await page.locator('.nearby-card').first().boundingBox();
  assert.ok(firstUnlinked.y + 80 < 781);
  assert.match(await page.locator('.nearby-card').first().textContent(), /Not connected/);
  await page.screenshot({ path: '/tmp/thoughtos-feedback-neighbors.png' });
  await page.locator('[data-neighbors="unlinked"]').click(); assert.equal(await page.locator('.around-card').count(), 14);
  assert.equal(await page.locator('.branch-card').count(), 0);
  const destination = await page.locator('.nearby-card [data-hop]').first().getAttribute('data-hop');
  await page.locator('.nearby-card [data-hop]').first().click();
  assert.notEqual(await page.locator('.chain-focus h2').textContent(), 'Small notes, big connections');
  const persisted = await page.evaluate(() => localStorage.getItem('thoughtos.visual-garden.v1'));
  assert.equal(persisted, null, 'Wandering never creates a link or writes notes');
  await page.locator('#back').click(); assert.equal(await page.locator('.chain-focus h2').textContent(), 'Small notes, big connections');
  await page.locator('[data-neighbors="all"]').click();
  await page.locator('.orbit-layout [data-name-link="n1"]').click();
  assert.equal(await page.locator('#relationship-label').inputValue(), '', 'Legacy reason is not invented');
  await page.locator('#relationship-label').fill('develops this idea');
  await page.locator('#relationship-form .capture-button').click();
  assert.match(await page.locator('.branch-card[data-hop="n1"] .relation-caption').textContent(), /develops this idea/);
  assert.match(await page.locator('.branch-card[data-hop="n1"] .similarity-caption').textContent(), /Shared #connections/);
  await page.screenshot({ path: '/tmp/thoughtos-centered-reasons.png' });

  // Collection drawer dismisses by Escape and closes after a filter is chosen.
  await page.locator('#toggle-sidebar').click(); assert.equal(await page.locator('#sidebar').isVisible(), true);
  assert.equal(await page.locator('main').evaluate(e => e.inert), true);
  await page.keyboard.press('Escape'); assert.equal(await page.locator('#sidebar').isVisible(), false);
  await page.locator('#toggle-sidebar').click(); await page.locator('[data-topic="Wardrub"]').click();
  assert.equal(await page.locator('#sidebar').isVisible(), false); assert.equal(await page.locator('.note-card').count(), 4);
  await page.locator('#clear-filter').click();
  // A collection grows only when its first note is saved. Cancel does not leave empty navigation.
  await page.locator('#toggle-sidebar').click(); await page.locator('#new-collection').click();
  await page.locator('[name="topic"]').fill('Cancelled collection'); await page.keyboard.press('Escape');
  assert.equal(await page.locator('[data-topic="Cancelled collection"]').count(), 0);
  await page.locator('#toggle-sidebar').click(); await page.locator('#new-collection').click();
  await page.locator('[name="topic"]').fill('Writing practice'); await page.locator('[name="body"]').fill('Try writing one page before breakfast.');
  await page.locator('#tag-input').fill('morning-pages'); await page.locator('#add-tag').click();
  await page.keyboard.press('Meta+s'); await page.locator('#close-reader').click();
  await page.locator('#toggle-sidebar').click();
  assert.equal(await page.locator('[data-topic="Writing practice"] small').textContent(), '1');
  await page.locator('[data-topic="Writing practice"]').click(); assert.equal(await page.locator('.note-card').count(), 1);
  await page.locator('#new-note').click(); await page.locator('[name="body"]').fill('Leave the next page unfinished.'); await page.keyboard.press('Meta+s');
  await page.reload(); await page.locator('#toggle-sidebar').click();
  assert.equal(await page.locator('[data-topic="Writing practice"] small').textContent(), '2');
  await page.locator('#close-sidebar').click();
  // Word cloud has a dedicated surface, counts new tags, and reveals matching notes.
  await page.locator('[data-view="cloud"]').click();
  assert.equal(await page.locator('#sidebar').isVisible(), false);
  assert.equal(await page.locator('[data-cloud-tag="morning-pages"]').count(), 1);
  const words = await page.locator('.cloud-word').evaluateAll(es => es.map(e => ({ ...e.getBoundingClientRect().toJSON(), font: parseFloat(getComputedStyle(e).fontSize), count: Number(e.dataset.count) })));
  for (let i = 0; i < words.length; i++) for (let j = i+1; j < words.length; j++) {
    const a=words[i], b=words[j];
    assert.ok(!(a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top), 'Cloud words do not overlap');
  }
  assert.ok(Math.max(...words.map(w=>w.font)) > Math.min(...words.map(w=>w.font))*2);
  await page.screenshot({ path: '/tmp/thoughtos-feedback-cloud.png' });
  await page.locator('[data-cloud-tag="morning-pages"]').click();
  assert.equal(await page.locator('#cloud-results .note-card').count(), 1);
  await page.locator('#cloud-results .card-open').click(); assert.equal(await page.locator('#inspector').isVisible(), true);
  await page.locator('#close-reader').click();
  // Mobile cloud, drawer and unconnected browsing fit the viewport.
  await page.setViewportSize({ width: 390, height: 844 }); await page.locator('#clear-cloud').click(); await page.evaluate(()=>scrollTo(0,0));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: '/tmp/thoughtos-feedback-cloud-mobile.png' });
  await page.locator('[data-view="desk"]').click(); await page.locator('[data-explore="n3"]').first().click();
  await page.locator('[data-neighbors="unlinked"]').click();
  assert.equal(await page.locator('.nearby-card').count(), 16);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: '/tmp/thoughtos-feedback-neighbors-mobile.png', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('PASS: all five feedback items: nearby unconnected notes, cloud, minimal chrome, collapsible sidebar, growing collections; desktop/mobile and persistence');
} finally { await browser.close(); }
