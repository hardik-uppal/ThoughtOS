import { STORAGE_KEY, TOPICS, freshNotes, related, filtered, topicsCloud, addLink, removeLink, migrateNotes, validateGraph, describeLink, renameLink, edges, deriveMetadata, normalisePrefs, parseSearch, cosine, semanticMatches, collectionNames, normaliseCollection, surroundingNotes } from './model.js';
import { PREFS_KEY, readExperiments, saveExperiment, deleteExperiment } from './experiments.js';

const $ = s => document.querySelector(s);
const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
document.querySelectorAll('[data-key]').forEach(el => { el.textContent = `${isMac ? '⌘' : 'Ctrl'} ${el.dataset.key}`; });
let prefs = normalisePrefs();
let prefsBlocked = false;
try { const raw = localStorage.getItem(PREFS_KEY); if (raw) prefs = normalisePrefs(JSON.parse(raw)); } catch { prefsBlocked = true; }
let notes = migrateNotes(freshNotes());
let legacyBackup = null;
let vectors = {}, vectorCache = new Map(), semanticEpoch = 0, semanticTimer, semanticQueue = Promise.resolve();
let events = [], relationPair = null, pendingRelation = { label: '', directed: false };
let storageBlocked = false;
try {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    const parsed = JSON.parse(saved);
    if (![1, 2].includes(parsed.version) || !validateGraph(parsed.notes)) throw new Error('Invalid saved garden');
    notes = migrateNotes(parsed.notes);
    if (parsed.version === 1) legacyBackup = saved;
  }
} catch {
  storageBlocked = true;
  $('#storage-warning').hidden = false;
  $('#storage-warning').textContent = 'Saved browser data could not be loaded. Your stored data has not been overwritten. Demo edits are temporary until you reset.';
}
const state = { sidebar: false, neighbors: 'all', cloudTag: '', reader: false, view: 'desk', query: '', topic: '', tag: '', selected: notes[0].id, history: [notes[0].id], cursor: 0 };
const undoStack = [];
let editing = null, editingTags = [], pendingLinkSource = null, picker = null, toastTimer;
const color = note => { const index = TOPICS.indexOf(note.topic); return ['peach', 'sage', 'butter', 'lavender'][index >= 0 ? index : [...note.topic].reduce((v,c) => v + c.codePointAt(0), 0) % 4]; };
const visible = () => {
  const items = filtered(notes, state);
  if (prefs.arrange === 'collection') return items.sort((a,b) => a.topic.localeCompare(b.topic));
  if (prefs.arrange === 'meaning') return items.sort((a,b) => proximity(b, selected()) - proximity(a, selected()));
  return items.sort((a,b) => b.createdAt.localeCompare(a.createdAt));
};
const selected = () => notes.find(n => n.id === state.selected);
const number = note => String(notes.findIndex(n => n.id === note.id) + 1).padStart(2, '0');
function toast(message) {
  $('#toast').textContent = message; $('#toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4500);
}
function save() {
  if (storageBlocked) { toast('Changed for this visit only; browser storage is unavailable.'); return; }
  try {
    if (legacyBackup) { localStorage.setItem(`${STORAGE_KEY}.pre-v3`, legacyBackup); legacyBackup = null; }
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 2, notes }));
  }
  catch {
    storageBlocked = true; $('#storage-warning').hidden = false;
    $('#storage-warning').textContent = 'Browser storage is unavailable or full. Changes will not survive a reload.';
    toast('Could not save to browser storage; changes are temporary.');
  }
}
function commit(next, message) {
  undoStack.push(structuredClone(notes)); if (undoStack.length > 30) undoStack.shift();
  if (!validateGraph(next)) { undoStack.pop(); toast('Invalid edit; your notes were preserved.'); return; }
  notes = next; vectors = {}; semanticEpoch++; toast(message); save(); render();
  recordAction(message);
  if (prefs.semantic) scheduleSemantic();
}
function focusThought() {
  const target = state.view === 'chain' ? $('.chain-focus h2') : $('#inspector h2');
  target?.focus({ preventScroll: true });
  // The narrow-screen reader floats over the desk without moving its scroll position.
}
function selectNote(id, { chain = false, focus = true } = {}) {
  if (!notes.some(n => n.id === id)) return;
  if (chain) state.view = 'chain';
  state.reader = !chain;
  state.selected = id;
  if (state.history[state.cursor] !== id) {
    state.history = [...state.history.slice(0, state.cursor + 1), id].slice(-50);
    state.cursor = state.history.length - 1;
  }
  render();
  $('#announcement').textContent = `Opened ${selected().title}. ${related(notes, id).length} connected thoughts.`;
  if (focus) focusThought();
}
function goHistory(index) {
  if (index < 0 || index >= state.history.length) return;
  state.cursor = index; state.selected = state.history[index]; state.reader = state.view !== 'chain'; render(); focusThought();
}
function setFilter(kind, value) { state[kind] = state[kind] === value ? '' : value; state.view = 'desk'; state.reader = false; setSidebar(false); render(); }
function clearFilters() { state.query = ''; state.topic = ''; state.tag = ''; $('#search').value = ''; render(); }
function renderSidebar() {
  $('#collections').innerHTML = `<button data-topic="" class="collection ${!state.topic ? 'active' : ''}" aria-pressed="${!state.topic}"><span>All notes</span><small>${notes.length}</small></button>` + collectionNames(notes).map(topic => `<button data-topic="${esc(topic)}" class="collection ${state.topic === topic ? 'active' : ''}" aria-pressed="${state.topic === topic}"><span><i class="topic-dot ${color({topic})}"></i>${esc(topic)}</span><small>${notes.filter(n => n.topic === topic).length}</small></button>`).join('');
  $('#corner-label').textContent = state.view === 'chain' ? selected().title : state.topic || 'All notes';
}
function setSidebar(open) {
  state.sidebar = open; $('.main').inert = open;
  $('#sidebar').hidden = !open; $('#drawer-scrim').hidden = !open;
  $('#toggle-sidebar').setAttribute('aria-expanded', String(open));
  document.body.classList.toggle('drawer-open', open);
  if (!open && $('#sidebar').contains(document.activeElement)) $('#toggle-sidebar').focus();
}
function renderJourney() {
  $('#journey').innerHTML = `<div class="journey-controls"><button id="back" aria-label="Previous thought" title="Back · Alt+Left" ${state.cursor === 0 ? 'disabled' : ''}>←</button><button id="forward" aria-label="Next thought in history" title="Forward · Alt+Right" ${state.cursor >= state.history.length - 1 ? 'disabled' : ''}>→</button></div><span class="journey-label">YOUR TRAIL</span><div class="journey-crumbs">${state.history.map((id, i) => { const n = notes.find(n => n.id === id); const linked = i > 0 && related(notes, state.history[i - 1]).some(r => r.id === id); return `${i ? `<span title="${linked ? 'Connected step' : 'Jump, not a connection'}">${linked ? '→' : '⋯'}</span>` : ''}<button data-history="${i}" ${i === state.cursor ? 'aria-current="step"' : ''} class="${i > state.cursor ? 'future-step' : ''}">${esc(n.title)}</button>`; }).join('')}</div>`;
  const crumbs = $('.journey-crumbs'), current = $('#journey [aria-current]');
  if (crumbs && current) {
    const c = crumbs.getBoundingClientRect(), r = current.getBoundingClientRect();
    if (r.right > c.right) crumbs.scrollLeft += r.right - c.right;
    else if (r.left < c.left) crumbs.scrollLeft -= c.left - r.left;
  }
}
function actions(note, { explore = true } = {}) {
  return `<div class="card-actions"><button data-edit="${esc(note.id)}" title="Edit this note">Edit</button><button data-connect="${esc(note.id)}">＋ Connect</button>${explore ? `<button data-explore="${esc(note.id)}" title="Follow this thought’s connections">Explore ↗</button>` : ''}</div>`;
}
function card(note, index) {
  return `<article class="note-card ${color(note)} ${note.id === state.selected ? 'selected' : ''}" style="--tilt:${[-.6, .5, -.4, .7][index % 4]}deg"><button class="card-open" data-open="${esc(note.id)}" aria-label="Open ${esc(note.title)}" aria-pressed="${note.id === state.selected}"><span class="card-top"><span>${esc(note.topic)}</span><span>${number(note)} /</span></span><h2>${esc(note.title)}</h2><p>${esc(note.body.split('\n\n')[0])}</p></button><div class="card-bottom"><span>${note.tags.slice(0, 2).map(t => `#${esc(t)}`).join(' &nbsp; ')}</span><button data-explore="${esc(note.id)}" aria-label="Explore ${related(notes, note.id).length} connections from ${esc(note.title)}">↔ ${related(notes, note.id).length} links</button></div>${actions(note)}</article>`;
}
function aroundCard({ note, linked, tags, semantic, position = 0 }) {
  const reason = linked ? describeLink(notes, state.selected, note.id) : '';
  const connection = linked ? edges(notes).find(e => (e.source === state.selected && e.target === note.id) || (e.target === state.selected && e.source === note.id)) : null;
  const unnamed = linked && !connection?.label;
  const tone = tags.length ? 'tags' : semantic ? 'meaning' : 'other';
  const similarity = tags.length ? `Shared ${tags.map(t => '#' + t).join(' · ')}` : semantic ? 'Similar meaning · local model' : 'From another corner';
  const label = linked ? unnamed ? 'Connected · reason not named' : reason : 'Not connected';
  return `<article class="around-card tone-${tone} ${linked ? 'is-linked' : 'nearby-card'}" style="--order:${position}"><button class="around-open ${linked ? 'branch-card' : ''}" data-hop="${esc(note.id)}"><span class="relation-caption">${esc(label)}</span><strong>${esc(note.title)}</strong><span class="around-excerpt">${esc(note.body.split('\n\n')[0])}</span><span class="similarity-caption">${esc(similarity)}</span></button><div class="around-actions"><button data-read-other="${esc(note.id)}" aria-label="Read ${esc(note.title)}">Read</button>${linked ? `<button data-name-link="${esc(note.id)}" aria-label="${unnamed ? 'Add' : 'Edit'} connection reason for ${esc(note.title)}">${unnamed ? '＋ Add reason' : 'Edit reason'}</button>` : `<button class="suggest-connect" data-suggest-connect="${esc(note.id)}" aria-label="Connect to ${esc(note.title)}">＋ Connect</button>`}</div></article>`;
}
function renderChain() {
  const note = selected(), links = related(notes, note.id);
  const items = surroundingNotes(notes, note.id, { scope: state.neighbors, vectors: prefs.semantic ? vectors : {} }).map((item, position) => ({ ...item, position }));
  const left = items.filter((_, i) => i % 4 < 2), right = items.filter((_, i) => i % 4 >= 2);
  return `<div class="chain-board"><div class="around-heading"><div class="similarity-key" aria-label="Note colour indicates similarity, not a connection"><span class="key-tags">Shared tags</span><span class="key-meaning">Similar meaning</span><span class="key-other">Elsewhere</span></div><div class="neighbor-scopes" role="group" aria-label="Nearby notes"><button data-neighbors="all" aria-pressed="${state.neighbors === 'all'}">All <small>${notes.length - 1}</small></button><button data-neighbors="unlinked" aria-pressed="${state.neighbors === 'unlinked'}">Unconnected <small>${notes.length - 1 - links.length}</small></button><button data-neighbors="linked" aria-pressed="${state.neighbors === 'linked'}">Connected <small>${links.length}</small></button></div></div><div class="orbit-layout around-grid"><article class="chain-focus"><div class="focus-top"><button id="all-cards">← All notes</button><span>${esc(note.topic)}</span></div><h2 tabindex="-1">${esc(note.title)}</h2><div class="focus-body">${esc(note.body)}</div><div class="focus-tags">${note.tags.map(t => `<button data-tag="${esc(t)}">#${esc(t)}</button>`).join('')}</div><div class="focus-actions"><button data-edit="${esc(note.id)}">Edit</button><button data-read="${esc(note.id)}">Read / connections</button><button data-connect="${esc(note.id)}">＋ Connect</button></div></article><section class="orbit-wing orbit-left" aria-label="Nearby thoughts to the left">${left.map(aroundCard).join('')}</section><section class="orbit-wing orbit-right" aria-label="Nearby thoughts to the right">${right.map(aroundCard).join('')}</section></div>${!items.length ? '<p class="small-muted">Nothing in this view yet. Choose All to keep wandering.</p>' : ''}</div>`;
}
function renderCloud() {
  const words = topicsCloud(notes), matches = state.cloudTag ? filtered(notes, { tag: state.cloudTag }) : [];
  return `<section class="cloud-space"><div class="cloud-title"><span>ON YOUR MIND</span><h1>A few things<br> <em>keep coming back.</em></h1><p>Pick a word. See where it takes you.</p></div><div id="cloud" class="word-cloud" aria-label="Explore tags">${words.slice(0,60).map(([tag,count],i) => `<button class="cloud-word cloud-ink-${i % 5} ${state.cloudTag === tag ? 'active' : ''}" data-cloud-tag="${esc(tag)}" data-count="${count}" aria-pressed="${state.cloudTag === tag}" aria-label="${esc(tag)}, ${count} notes"><span>${esc(tag)}</span><sup>${count}</sup></button>`).join('')}</div><p class="cloud-footnote">${words.length ? 'Bigger words appear in more notes. The cloud grows with your tags.' : 'Add a tag to a note and it will appear here.'}</p>${words.length > 60 ? `<details class="more-tags"><summary>All ${words.length} tags</summary>${words.map(([t,c]) => `<button data-cloud-tag="${esc(t)}">${esc(t)} · ${c}</button>`).join('')}</details>` : ''}</section><section id="cloud-results" class="cloud-results" aria-live="polite">${state.cloudTag ? `<div class="cloud-result-heading"><h2>#${esc(state.cloudTag)} <small>${matches.length} notes</small></h2><button id="clear-cloud" aria-label="Clear cloud selection">×</button></div><div class="desk-grid">${matches.map(card).join('')}</div>` : ''}</section>`;
}
function layoutCloud() {
  const cloud = $('#cloud'); if (!cloud) return;
  const width = cloud.clientWidth, height = width < 500 ? 460 : 430;
  const words = [...cloud.querySelectorAll('.cloud-word')], bounds = [];
  const context = document.createElement('canvas').getContext('2d');
  const max = Math.max(1, ...words.map(w => Number(w.dataset.count)));
  let extraY = height;
  for (let i = 0; i < words.length; i++) {
    const word = words[i], count = Number(word.dataset.count), text = word.querySelector('span').textContent;
    let size = (width < 500 ? 13 : 15) + (width < 500 ? 21 : 45) * (count / max) ** 2;
    size = Math.min(size, (width - 40) / Math.max(1, text.length * .65));
    const angle = [0,-5,4,0,7,-4,0][i % 7], rad = Math.abs(angle) * Math.PI / 180;
    context.font = `${i % 3 === 1 ? 'italic ' : ''}${size}px Georgia`;
    const tw = context.measureText(text).width + 22, th = size * 1.22 + 8;
    const bw = tw * Math.cos(rad) + th * Math.sin(rad), bh = tw * Math.sin(rad) + th * Math.cos(rad);
    let placed = null;
    for (let k = 0; k < 10000; k++) {
      const a = k * 2.399963, r = Math.sqrt(k) * 4;
      const cx = width / 2 + Math.cos(a) * r * 1.35, cy = height / 2 + Math.sin(a) * r * .8;
      const box = { x: cx - bw / 2, y: cy - bh / 2, w: bw, h: bh };
      if (box.x < 5 || box.y < 6 || box.x + bw > width - 5 || box.y + bh > height - 6) continue;
      if (bounds.some(b => box.x < b.x+b.w+5 && box.x+box.w+5 > b.x && box.y < b.y+b.h+5 && box.y+box.h+5 > b.y)) continue;
      placed = box; break;
    }
    if (!placed) { placed = { x: Math.max(5,(width-bw)/2), y: extraY+12, w:bw, h:bh }; extraY += bh+20; }
    bounds.push(placed);
    word.style.cssText = `left:${placed.x + placed.w/2}px;top:${placed.y + placed.h/2}px;font-size:${size}px;--turn:${angle}deg;--delay:${i*18}ms`;
  }
  cloud.style.height = `${extraY}px`;
}
function renderInspector() {
  $('#inspector').hidden = !state.reader;
  document.body.classList.toggle('reader-open', state.reader);
  const note = selected(), links = related(notes, note.id);
  const outside = state.view !== 'chain' && !visible().some(n => n.id === note.id);
  $('#inspector').innerHTML = `<div class="inspector-top"><span>OPEN THOUGHT</span><button id="close-reader" aria-label="Close reading panel">× Close</button></div><div class="inspector-toolbar"><button data-edit="${esc(note.id)}">✎ Edit note <kbd>E</kbd></button><button data-tags="${esc(note.id)}"># Tags <kbd>T</kbd></button></div><div class="inspector-paper ${color(note)}"><div class="card-top"><span>${esc(note.topic)}</span></div><h2 tabindex="-1">${esc(note.title)}</h2><div class="note-body">${note.body.split('\n\n').map(p => `<p>${esc(p)}</p>`).join('')}</div><div class="note-tags">${note.tags.map(t => `<button data-tag="${esc(t)}" title="Filter desk by ${esc(t)}">#${esc(t)}</button>`).join('')}<button class="tag-add" data-tags="${esc(note.id)}">＋ Add tag</button></div></div>${outside ? '<p class="outside-filter">This open thought is outside the desk filter. <button id="reveal-note">Clear filters to show it</button></p>' : ''}<section class="connections"><div class="connections-title"><h3>Connected thoughts <span>${links.length}</span></h3><button data-explore="${esc(note.id)}" class="text-button">Explore chain ↗</button></div><button class="connect-primary" id="connect-note" data-connect="${esc(note.id)}">＋ Connect a thought <kbd>C</kbd></button><p class="small-muted">Choose another card. A link appears on both.</p>${links.map(n => `<div class="connection-row"><button data-hop="${esc(n.id)}"><span class="thread-line">↔</span><span>${esc(n.title)}<small>${esc(describeLink(notes, note.id, n.id))}</small></span><span>→</span></button><button class="name-link" data-name-link="${esc(n.id)}" aria-label="Name connection to ${esc(n.title)}">Name</button><button class="unlink" data-unlink="${esc(n.id)}" aria-label="Remove connection to ${esc(n.title)}" title="Remove connection (undo available)">×</button></div>`).join('')}${!links.length ? '<p class="small-muted">No connections yet. Choose one above, or create a new connected thought.</p>' : ''}</section>`;
}
function renderWorkspace() {
  const items = visible();
  $('#workspace').className = `workspace view-${state.view}`;
  document.body.classList.toggle('exploring', state.view === 'chain');
  if (state.view === 'chain') $('#workspace').innerHTML = renderChain();
  else if (state.view === 'cloud') $('#workspace').innerHTML = renderCloud();
  else if (!items.length) $('#workspace').innerHTML = '<div class="empty-state"><span>✳</span><h2>A quiet corner.</h2><p>No notes match these filters. Try another word or show all cards.</p><button id="empty-clear" class="capture-button">Show all thoughts</button></div>';
  else if (state.view === 'desk') $('#workspace').innerHTML = `<div class="desk-grid">${items.map(card).join('')}</div>`;
  else $('#workspace').innerHTML = `<div class="notes-list">${items.map(n => `<div class="list-note ${n.id === state.selected ? 'active' : ''}"><button class="list-open" data-open="${esc(n.id)}"><span class="list-num">${number(n)}</span><span><strong>${esc(n.title)}</strong><small>${esc(n.topic)} · ${n.tags.map(t => `#${esc(t)}`).join(' ')}</small></span></button><button data-connect="${esc(n.id)}" class="text-button">＋ Connect</button><button data-explore="${esc(n.id)}" class="text-button">↔ ${related(notes, n.id).length} links</button></div>`).join('')}</div>`;
  $('#note-count').textContent = state.view === 'chain' ? `${related(notes, state.selected).length} connected thoughts · all collections` : `${items.length} of ${notes.length} demo thoughts`;
  $('#clear-filter').hidden = ['chain','cloud'].includes(state.view) || (!state.tag && !state.topic && !state.query);
  $('#clear-filter').textContent = `${state.tag ? `#${state.tag}` : state.topic || state.query} × Clear`;
  $('#view-hint').textContent = state.view === 'chain' ? 'Desk filters stay saved when you explore.' : '↑ ↓ ← → to move · Enter to open';
}
function render() {
  const focused = document.activeElement;
  const attr = ['data-open', 'data-connect', 'data-edit', 'data-tags', 'data-explore', 'data-topic', 'data-tag'].find(a => focused?.hasAttribute(a));
  const value = attr ? focused.getAttribute(attr) : null;
  const id = focused?.id;
  document.body.dataset.density = prefs.density;
  $('#arrange').value = prefs.arrange;
  renderSidebar(); renderWorkspace(); renderInspector(); renderJourney();
  $('#journey').hidden = state.view !== 'chain';
  document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === state.view)));
  $('#undo').disabled = !undoStack.length;
  $('.workspace-meta').hidden = $('#clear-filter').hidden;
  if (state.view === 'cloud') layoutCloud();
  if (focused !== document.activeElement) {
    const replacement = id ? document.getElementById(id) : attr ? document.querySelector(`[${attr}="${CSS.escape(value)}"]`) : null;
    replacement?.focus({ preventScroll: true });
  }
}
function renderEditingTags() {
  $('#editing-tags').innerHTML = editingTags.map(t => `<button type="button" data-remove-tag="${esc(t)}" aria-label="Remove tag ${esc(t)}">#${esc(t)} <span>×</span></button>`).join('');
  $('#editor-form').elements.tags.value = editingTags.join(', ');
  $('#tag-suggestions').innerHTML = '<span>Reuse a tag:</span>' + topicsCloud(notes).filter(([t]) => !editingTags.includes(t)).slice(0, 8).map(([t]) => `<button type="button" data-add-tag="${esc(t)}">#${esc(t)}</button>`).join('');
}
function addTags(value) {
  const incoming = value.split(',').map(t => t.trim().replace(/^#+/, '').toLowerCase().slice(0, 40)).filter(Boolean);
  if (new Set([...editingTags, ...incoming]).size > 12) toast('Up to 12 tags per thought.');
  editingTags = [...new Set([...editingTags, ...incoming])].slice(0, 12);
  $('#tag-input').value = ''; renderEditingTags(); renderMetadata();
}
function openEditor(id = null, { tags = false, linkFrom = null, title = '' } = {}) {
  setSidebar(false);
  editing = id; pendingLinkSource = linkFrom;
  if (!linkFrom) pendingRelation = { label: '', directed: false };
  const note = notes.find(n => n.id === id), form = $('#editor-form');
  $('#editor-heading').textContent = note ? 'Edit thought' : linkFrom ? 'New connected thought' : 'New thought';
  $('#editor-eyebrow').textContent = linkFrom ? `WILL CONNECT TO: ${notes.find(n => n.id === linkFrom)?.title}` : 'ONE IDEA IS ENOUGH';
  form.elements.title.value = note?.title || title; form.elements.freeTitle.value = note?.title || title; form.elements.body.value = note?.body || '';
  editingTags = [...(note?.tags || [])]; $('#tag-input').value = ''; renderEditingTags(); renderMetadata();
  $('#collection-options').innerHTML = collectionNames(notes).map(t => `<option value="${esc(t)}"></option>`).join('');
  form.elements.topic.value = note?.topic || state.topic || '';
  $('#compose-mode').value = prefs.compose; applyComposeMode(tags); renderMetadata();
  $('#editor-dialog').showModal(); (tags ? $('#tag-input') : prefs.compose === 'freeform' ? form.elements.body : form.elements.title).focus();
}
function pickerItems() {
  const q = $('#picker-search').value.trim();
  const source = notes.find(n => n.id === picker.source);
  const connected = source ? new Set(related(notes, source.id).map(n => n.id)) : new Set();
  const literal = filtered(notes, { query: q });
  const extra = picker.meaning || [];
  const combined = [...literal, ...extra.filter(n => !literal.some(l => l.id === n.id))];
  return combined.filter(n => picker.mode !== 'connect' || (n.id !== source?.id && !connected.has(n.id)))
    .sort((a, b) => (source ? b.tags.filter(t => source.tags.includes(t)).length - a.tags.filter(t => source.tags.includes(t)).length : 0));
}
function renderPicker() {
  const items = pickerItems(); picker.ids = items.map(n => n.id); picker.index = Math.min(Math.max(0, picker.index), Math.max(0, items.length - 1));
  const source = notes.find(n => n.id === picker.source);
  $('#picker-count').textContent = `${items.length} ${picker.mode === 'connect' ? 'available to connect' : 'thoughts found'}`;
  $('#picker-results').innerHTML = items.length ? items.map((n, i) => {
    const tags = source ? n.tags.filter(t => source.tags.includes(t)) : [];
    return `<button role="option" id="pick-${i}" aria-selected="${i === picker.index}" tabindex="-1" data-pick="${esc(n.id)}"><span class="pick-number ${color(n)}">${number(n)}</span><span class="pick-text"><strong>${esc(n.title)}</strong><small>${esc(n.topic)}${picker.meaning?.some(m => m.id === n.id) && !filtered([n], { query: $('#picker-search').value }).length ? ' · Similar meaning' : ''}${tags.length ? ` · shares ${tags.map(t => `#${esc(t)}`).join(', ')}` : ''}</small><span>${esc(n.body.slice(0, 100))}${n.body.length > 100 ? '…' : ''}</span></span><span class="pick-action">${picker.mode === 'connect' ? '＋ Connect' : 'Open ↗'}</span></button>`;
  }).join('') : '<p class="picker-empty">No matching thoughts. Try another word or write a new one.</p>';
  $('#picker-search').setAttribute('aria-activedescendant', items.length ? `pick-${picker.index}` : '');
}
function openPicker(mode = 'find', source = state.selected) {
  setSidebar(false);
  semanticEpoch++; picker = { mode, source, index: 0, ids: [], meaning: [] };
  $('#link-details').hidden = mode !== 'connect'; $('#link-label').value = ''; $('#link-directed').checked = false;
  $('#meaning-search').checked = prefs.semantic;
  $('#picker-heading').textContent = mode === 'connect' ? 'Connect a thought' : 'Find a thought';
  $('#picker-eyebrow').textContent = mode === 'connect' ? 'KEEP THE REASON, TOO.' : 'SEARCH EVERY THOUGHT';
  $('#picker-context').textContent = mode === 'connect' ? `From “${notes.find(n => n.id === source).title}” → choose a thought below. Existing connections are excluded.` : 'Search across all collections, regardless of desk filters.';
  $('#picker-search').value = ''; $('#picker-feedback').textContent = '';
  $('#new-linked').hidden = mode !== 'connect'; renderPicker(); $('#picker-dialog').showModal(); $('#picker-search').focus(); scheduleSemantic();
}
function pickNote(id) {
  if (!picker?.ids.includes(id)) return;
  const { mode, source } = picker;
  $('#picker-dialog').close();
  if (mode === 'connect') {
    const target = notes.find(n => n.id === id);
    commit(addLink(notes, source, id, $('#link-label').value, $('#link-directed').checked), `Connected to “${target.title}”. The link is visible on both thoughts.`);
    selectNote(source);
    if (prefs.semantic) scheduleSemantic();
  } else selectNote(id, { chain: true });
}
function undo() {
  if (!undoStack.length) return;
  notes = undoStack.pop();
  state.history = state.history.filter(id => notes.some(n => n.id === id));
  if (!state.history.length) state.history = [notes[0].id];
  state.cursor = Math.min(state.cursor, state.history.length - 1); state.selected = state.history[state.cursor];
  vectors = {}; semanticEpoch++; save(); render(); toast('Last edit undone.'); recordAction('Undo completed edit'); if (prefs.semantic) scheduleSemantic();
}
function moveCard(key) {
  const buttons = [...$('#workspace').querySelectorAll('[data-open], [data-hop]')];
  if (!buttons.length) return;
  const current = buttons.indexOf(document.activeElement);
  if (current < 0) { buttons[0].focus(); return; }
  const rect = buttons[current].getBoundingClientRect(), cx = rect.x + rect.width / 2, cy = rect.y + rect.height / 2;
  const horizontal = key === 'ArrowLeft' || key === 'ArrowRight';
  const sign = key === 'ArrowLeft' || key === 'ArrowUp' ? -1 : 1;
  const candidates = buttons.filter(b => b !== buttons[current]).map(button => {
    const r = button.getBoundingClientRect(), dx = r.x + r.width / 2 - cx, dy = r.y + r.height / 2 - cy;
    const primary = horizontal ? dx : dy, secondary = horizontal ? dy : dx;
    return { button, primary: primary * sign, score: Math.abs(primary) + Math.abs(secondary) * 3 };
  }).filter(b => b.primary > 10).sort((a, b) => a.score - b.score);
  candidates[0]?.button.focus();
}
document.addEventListener('click', event => {
  const b = event.target.closest('button'); if (!b) return;
  if ($('#desk-menu').contains(b)) $('#desk-menu').open = false;
  if (b.dataset.close) $(`#${b.dataset.close}`).close();
  else if (b.dataset.view) { state.view = b.dataset.view; state.reader = false; setSidebar(false); render(); }
  else if (b.dataset.neighbors) { state.neighbors = b.dataset.neighbors; render(); }
  else if (b.dataset.cloudTag) { state.cloudTag = state.cloudTag === b.dataset.cloudTag ? '' : b.dataset.cloudTag; render(); $('#cloud-results').scrollIntoView({ block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); }
  else if (b.dataset.readOther) { state.reader = true; selectNote(b.dataset.readOther); }
  else if (b.dataset.read) { state.reader = true; render(); $('#inspector h2').focus(); }
  else if (b.dataset.nameLink) openRelationship(b.dataset.nameLink);
  else if (b.dataset.snapshotRestore) restoreSnapshot(b.dataset.snapshotRestore);
  else if (b.dataset.snapshotDelete) { if (confirm('Delete this snapshot? This cannot be undone.')) { try { deleteExperiment(localStorage, b.dataset.snapshotDelete); renderSnapshots(); } catch (e) { snapshotError(e); } } }
  else if (b.dataset.metadataTag) addTags(b.dataset.metadataTag);
  else if (b.dataset.open) selectNote(b.dataset.open);
  else if (b.dataset.hop) selectNote(b.dataset.hop, { chain: true });
  else if (b.dataset.explore) selectNote(b.dataset.explore, { chain: true });
  else if (b.dataset.connect) openPicker('connect', b.dataset.connect);
  else if (b.dataset.edit) openEditor(b.dataset.edit);
  else if (b.dataset.tags) openEditor(b.dataset.tags, { tags: true });
  else if (b.dataset.pick) pickNote(b.dataset.pick);
  else if (b.dataset.suggestConnect) { openPicker('connect', state.selected); $('#picker-search').value = notes.find(n => n.id === b.dataset.suggestConnect).title; renderPicker(); }
  else if (b.dataset.removeTag) { editingTags = editingTags.filter(t => t !== b.dataset.removeTag); renderEditingTags(); $('#tag-input').focus(); }
  else if (b.dataset.addTag) { addTags(b.dataset.addTag); $('#tag-input').focus(); }
  else if (b.hasAttribute('data-topic')) setFilter('topic', b.dataset.topic);
  else if (b.hasAttribute('data-tag')) setFilter('tag', b.dataset.tag);
  else if (b.hasAttribute('data-history')) goHistory(Number(b.dataset.history));
  else if (b.dataset.unlink) commit(removeLink(notes, state.selected, b.dataset.unlink), 'Connection removed from both notes. Undo is available.');
  else switch (b.id) {
    case 'toggle-sidebar': setSidebar(!state.sidebar); if (state.sidebar) $('#close-sidebar').focus(); break;
    case 'close-sidebar': case 'drawer-scrim': setSidebar(false); $('#toggle-sidebar').focus(); break;
    case 'clear-cloud': state.cloudTag = ''; render(); break;
    case 'new-collection': setSidebar(false); openEditor(); $('#capture-details').open = true; $('#editor-form').elements.topic.value = ''; $('#editor-form').elements.topic.focus(); toast('Name a collection and save its first note.'); break;
    case 'close-reader': state.reader = false; render(); ($(`[data-open="${CSS.escape(state.selected)}"]`) || $('#workspace')).focus(); break;
    case 'settings': $('#density').value = prefs.density; $('#semantic-pref').checked = prefs.semantic; $('#record-pref').checked = prefs.record; $('#settings-dialog').showModal(); break;
    case 'experiments': renderSnapshots(); $('#experiments-dialog').showModal(); break;
    case 'suggest-title': { const title = deriveMetadata($('#editor-form').elements.body.value, notes).title; $('#editor-form').elements.title.value = title; $('#editor-form').elements.freeTitle.value = title; toast('Suggested title applied.'); break; }
    case 'new-note': openEditor(); break;
    case 'find-note': openPicker(); break;
    case 'help': $('#help-dialog').showModal(); break;
    case 'source-info': $('#sources-dialog').showModal(); break;

    case 'clear-filter': case 'empty-clear': case 'reveal-note': clearFilters(); break;
    case 'all-cards': state.view = 'desk'; render(); break;
    case 'back': goHistory(state.cursor - 1); break;
    case 'forward': goHistory(state.cursor + 1); break;
    case 'add-tag': addTags($('#tag-input').value); $('#tag-input').focus(); break;
    case 'new-linked': { const source = picker.source, title = $('#picker-search').value.trim(); pendingRelation = { label: $('#link-label').value, directed: $('#link-directed').checked }; $('#picker-dialog').close(); openEditor(null, { linkFrom: source, title }); break; }
    case 'wander': { const pool = (state.view === 'chain' ? notes : visible()).filter(n => n.id !== state.selected); if (pool.length) selectNote(pool[Math.floor(Math.random() * pool.length)].id, { chain: true }); else toast('Clear the desk filters to find another thought.'); break; }
    case 'undo': undo(); break;
    case 'reset': {
      if (!confirm('Reset this browser’s demo notes? Your prototype edits will be removed. Real ThoughtOS notes are never touched.')) break;
      try { localStorage.removeItem(STORAGE_KEY); storageBlocked = false; $('#storage-warning').hidden = true; } catch { /* Retain in-memory mode. */ }
      notes = migrateNotes(freshNotes()); vectors = {}; semanticEpoch++; state.reader = false; undoStack.length = 0; state.view = 'desk'; state.cloudTag = ''; state.selected = notes[0].id; state.history = [state.selected]; state.cursor = 0;
      save(); clearFilters(); toast('Demo desk reset. Snapshots were kept.'); recordAction('Reset demo desk'); if (prefs.semantic) scheduleSemantic(); break;
    }
  }
});
$('#search').addEventListener('input', event => { state.query = event.target.value; state.view = 'desk'; render(); });
$('#picker-search').addEventListener('input', () => { picker.index = 0; picker.meaning = []; renderPicker(); scheduleSemantic(); });
$('#picker-search').addEventListener('keydown', event => {
  if (event.isComposing) return;
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault(); picker.index = Math.max(0, Math.min(picker.ids.length - 1, picker.index + (event.key === 'ArrowDown' ? 1 : -1)));
    renderPicker(); document.getElementById(`pick-${picker.index}`)?.scrollIntoView({ block: 'nearest' });
  } else if (event.key === 'Enter') { event.preventDefault(); pickNote(picker.ids[picker.index]); }
});
$('#tag-input').addEventListener('keydown', event => { if (!event.isComposing && (event.key === 'Enter' || event.key === ',')) { event.preventDefault(); addTags(event.target.value); } });
$('#editor-form').addEventListener('submit', event => {
  event.preventDefault(); addTags($('#tag-input').value);
  const data = new FormData(event.target);
  const title = (prefs.compose === 'freeform' ? data.get('freeTitle') : data.get('title')).trim() || deriveMetadata(data.get('body'), notes).title;
  if (!title) { toast('Write a thought or give it a title first.'); event.target.elements.body.focus(); return; }
  const changes = { title, body: data.get('body'), topic: normaliseCollection(data.get('topic'), notes), tags: [...editingTags] };
  const uid = crypto.randomUUID?.() || [...crypto.getRandomValues(new Uint8Array(16))].map(b => b.toString(16).padStart(2, '0')).join('');
  const id = editing || `note-${uid}`;
  let next = editing ? notes.map(n => n.id === id ? { ...n, ...changes } : n) : [...notes, { id, ...changes, links: [], aside: '', createdAt: new Date().toISOString() }];
  if (pendingLinkSource) next = addLink(next, pendingLinkSource, id, pendingRelation.label, pendingRelation.directed);
  if (!validateGraph(next)) { toast('This prototype supports up to 500 notes.'); return; }
  const isLinked = Boolean(pendingLinkSource);
  $('#editor-dialog').close(); commit(next, isLinked ? 'Thought saved and connected in both directions.' : 'Thought saved.'); selectNote(id, { chain: isLinked || state.view === 'chain' });
});
document.addEventListener('keydown', event => {
  if (event.isComposing) return;
  const key = event.key.toLowerCase(), mod = event.metaKey || event.ctrlKey;
  if ($('#editor-dialog').open && mod && key === 's') { event.preventDefault(); $('#editor-form').requestSubmit(); return; }
  if (document.querySelector('dialog[open]')) return;
  if (mod && ['f', 'k'].includes(key)) { event.preventDefault(); openPicker(); return; }
  if (mod && key === 'n') { event.preventDefault(); openEditor(); return; }
  if (key === 'escape' && state.sidebar) { event.preventDefault(); setSidebar(false); $('#toggle-sidebar').focus(); return; }
  const typing = event.target.closest('input,textarea,select,[contenteditable="true"]');
  if (typing) return;
  if (event.altKey && ['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); goHistory(state.cursor + (event.key === 'ArrowLeft' ? -1 : 1)); return; }
  if (mod || event.altKey) return;
  if (key === 'escape' && state.reader) { $('#close-reader').click(); return; }
  const shortcuts = { b: () => { setSidebar(!state.sidebar); if (state.sidebar) $('#close-sidebar').focus(); }, f: () => openPicker(), '/': () => openPicker(), n: () => openEditor(), e: () => openEditor(state.selected), t: () => openEditor(state.selected, { tags: true }), c: () => openPicker('connect'), x: () => selectNote(state.selected, { chain: true }), '?': () => $('#help-dialog').showModal() };
  if (shortcuts[key]) { event.preventDefault(); shortcuts[key](); }
  else if (event.key.startsWith('Arrow') && $('#workspace').contains(event.target)) { event.preventDefault(); moveCard(event.key); }
});
function persistPrefs() {
  if (prefsBlocked) { toast('Settings could not be loaded; stored settings were preserved.'); return; }
  try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs)); }
  catch { toast('Settings could not be saved; they apply to this visit only.'); }
}
function applyComposeMode(tags = false) {
  const free = prefs.compose === 'freeform';
  $('#title-field').hidden = free; $('#freeform-title').hidden = !free;
  $('#capture-details').open = !free || tags;
}
function renderMetadata() {
  const metadata = deriveMetadata($('#editor-form').elements.body.value, notes);
  $('#metadata-review').hidden = !metadata.title;
  $('#suggest-title').textContent = `Use title: ${metadata.title}`;
  $('#suggested-tags').innerHTML = metadata.tags.filter(t => !editingTags.includes(t)).map(t => `<button type="button" data-metadata-tag="${esc(t)}">＋ #${esc(t)}</button>`).join('');
}
function recordAction(action) {
  if (!prefs.record) return;
  events = [...events, { action: action.slice(0, 300), at: new Date().toISOString() }].slice(-200);
  try { saveExperiment(localStorage, { title: action, kind: 'auto', notes, prefs, events }); }
  catch (e) { toast(`Edit kept, but recording failed: ${e.message}`); }
}
function snapshotError(error) { $('#snapshot-status').textContent = `Could not complete snapshot action: ${error.message}`; }
function renderSnapshots() {
  $('#snapshot-status').textContent = '';
  try {
    const snapshots = readExperiments(localStorage);
    $('#snapshot-list').innerHTML = snapshots.length ? snapshots.map(s => `<article class="snapshot-row"><div><strong>${esc(s.title)}</strong><small>${esc(s.kind)} · ${new Date(s.createdAt).toLocaleString()} · ${s.payload.notes.length} thoughts</small></div><button data-snapshot-restore="${esc(s.id)}">Restore</button><button data-snapshot-delete="${esc(s.id)}" aria-label="Delete snapshot ${esc(s.title)}">Delete</button></article>`).join('') : '<p class="small-muted">No snapshots yet. Name this desk before trying something new.</p>';
  } catch (e) { $('#snapshot-list').textContent = ''; snapshotError(e); }
}
function restoreSnapshot(id) {
  try {
    const snapshot = readExperiments(localStorage).find(s => s.id === id);
    if (!snapshot) throw new Error('Snapshot no longer exists.');
    if (storageBlocked) throw new Error('Resolve the browser-storage warning before restoring.');
    if (!confirm(`Restore “${snapshot.title}”? Your current desk will be saved as a safety copy first.`)) return;
    saveExperiment(localStorage, { title: `Before restoring ${snapshot.title}`.slice(0,120), kind: 'safety', notes, prefs, events });
    // Keep recording and local-model consent unchanged; restoring never opts the user in.
    prefs = { ...normalisePrefs(snapshot.payload.prefs), record: prefs.record, semantic: prefs.semantic };
    events = structuredClone(snapshot.payload.events || []);
    state.selected = snapshot.payload.notes[0].id; state.history = [state.selected]; state.cursor = 0; state.view = 'desk'; state.reader = false; state.cloudTag = '';
    state.query = ''; state.topic = ''; state.tag = ''; $('#search').value = '';
    persistPrefs(); commit(migrateNotes(snapshot.payload.notes), `Restored “${snapshot.title}”. Safety copy saved.`);
    renderSnapshots(); $('#snapshot-status').textContent = storageBlocked ? 'Restored in memory only; browser save failed. The safety copy was saved.' : `Restored “${snapshot.title}”. Open the safety copy to return to your previous desk.`;
  } catch (e) { snapshotError(e); }
}
function openRelationship(target) {
  const edge = edges(notes).find(e => (e.source === state.selected && e.target === target) || (e.target === state.selected && e.source === target));
  if (!edge) return;
  relationPair = [edge.source, edge.target];
  $('#relationship-context').textContent = `${notes.find(n => n.id === edge.source).title} → ${notes.find(n => n.id === edge.target).title}`;
  $('#relationship-label').value = edge.label; $('#relationship-directed').checked = edge.directed;
  $('#relationship-dialog').showModal(); $('#relationship-label').focus();
}
function proximity(note, source) {
  if (!source) return 0;
  if (note.id === source.id) return 100;
  if (prefs.semantic && vectors[note.id] && vectors[source.id]) return cosine(vectors[note.id], vectors[source.id]);
  return note.tags.filter(t => source.tags.includes(t)).length / Math.max(1, new Set([...note.tags, ...source.tags]).size);
}
async function requestEmbeddings(texts) {
  const response = await fetch('/api/semantic', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ texts }), signal: AbortSignal.timeout(35000) });
  if (!response.ok) throw new Error('Local meaning search unavailable. Text & tags still work.');
  const result = await response.json();
  if (result.error) throw new Error(result.error);
  if (!Array.isArray(result.embeddings) || result.embeddings.length !== texts.length) throw new Error('Invalid local model response.');
  return result.embeddings;
}
function scheduleSemantic() {
  const epoch = ++semanticEpoch;
  clearTimeout(semanticTimer);
  if (!prefs.semantic) { vectors = {}; if (picker) picker.meaning = []; setMeaningStatus('Text & tags'); return; }
  semanticTimer = setTimeout(() => {
    semanticQueue = semanticQueue.catch(() => {}).then(async () => {
      if (epoch !== semanticEpoch || !prefs.semantic) return;
      setMeaningStatus('Finding local meaning matches…');
      try {
        const corpus = notes.map(n => ({ id: n.id, text: `search_document: ${n.title}\n${n.body}\n${n.tags.join(' ')}` }));
        const missing = corpus.filter(n => !vectorCache.has(n.text));
        for (let i = 0; i < missing.length; i += 16) {
          if (epoch !== semanticEpoch || !prefs.semantic) return;
          const batch = missing.slice(i, i + 16), result = await requestEmbeddings(batch.map(n => n.text));
          batch.forEach((n, j) => vectorCache.set(n.text, result[j]));
        }
        if (epoch !== semanticEpoch || !prefs.semantic) return;
        const activeTexts = new Set(corpus.map(n => n.text));
        for (const key of vectorCache.keys()) if (!activeTexts.has(key)) vectorCache.delete(key);
        vectors = Object.fromEntries(corpus.map(n => [n.id, vectorCache.get(n.text)]));
        const query = $('#picker-search').value, text = parseSearch(query).text;
        if ($('#picker-dialog').open && text) {
          const [queryVector] = await requestEmbeddings([`search_query: ${text}`]);
          if (epoch !== semanticEpoch || !prefs.semantic) return;
          picker.meaning = semanticMatches(notes, vectors, queryVector, { query }).map(r => r.note);
        }
        setMeaningStatus('Local meaning + text & tags');
        if ($('#picker-dialog').open) renderPicker();
        render();
      } catch (e) {
        if (epoch !== semanticEpoch) return;
        vectors = {}; if (picker) picker.meaning = [];
        setMeaningStatus(e.message); if ($('#picker-dialog').open) renderPicker(); render();
      }
    });
  }, 350);
}
function setMeaningStatus(message) { $('#meaning-status').textContent = message; $('#arrange').title = prefs.arrange === 'meaning' ? `${Object.keys(vectors).length ? 'Local meaning' : 'Shared tags'} around the last selected thought` : ''; }
$('#editor-form').elements.body.addEventListener('input', renderMetadata);
$('#compose-mode').addEventListener('change', e => {
  const form = $('#editor-form');
  if (prefs.compose === 'freeform') form.elements.title.value = form.elements.freeTitle.value; else form.elements.freeTitle.value = form.elements.title.value;
  prefs.compose = e.target.value; persistPrefs(); applyComposeMode();
});
$('#density').addEventListener('change', e => { prefs.density = e.target.value; persistPrefs(); render(); });
$('#arrange').addEventListener('change', e => { prefs.arrange = e.target.value; persistPrefs(); render(); if (prefs.arrange === 'meaning') { toast(prefs.semantic ? 'Arranging similar thoughts around the last selected note.' : 'Arranged by shared tags around the last selected note.'); scheduleSemantic(); } });
function setSemantic(enabled) { prefs.semantic = enabled; persistPrefs(); $('#meaning-search').checked = enabled; $('#semantic-pref').checked = enabled; if (picker) picker.meaning = []; scheduleSemantic(); render(); if ($('#picker-dialog').open) renderPicker(); }
$('#meaning-search').addEventListener('change', e => setSemantic(e.target.checked));
$('#semantic-pref').addEventListener('change', e => setSemantic(e.target.checked));
$('#record-pref').addEventListener('change', e => { prefs.record = e.target.checked; if (!prefs.record) events = []; persistPrefs(); });
$('#snapshot-form').addEventListener('submit', e => {
  e.preventDefault();
  try { saveExperiment(localStorage, { title: $('#snapshot-title').value, notes, prefs, events }); $('#snapshot-title').value = ''; renderSnapshots(); $('#snapshot-status').textContent = 'Snapshot saved in this browser.'; }
  catch (error) { snapshotError(error); }
});
$('#relationship-form').addEventListener('submit', e => {
  e.preventDefault(); commit(renameLink(notes, ...relationPair, $('#relationship-label').value, $('#relationship-directed').checked), 'Connection meaning saved.'); $('#relationship-dialog').close();
});
render();
let cloudWidth = 0;
new ResizeObserver(() => { if (state.view === 'cloud' && $('#cloud')?.clientWidth !== cloudWidth) { cloudWidth = $('#cloud').clientWidth; layoutCloud(); } }).observe($('#workspace'));
document.addEventListener('click', e => { if (!$('#desk-menu').contains(e.target)) $('#desk-menu').open = false; });
if (prefs.semantic) scheduleSemantic();
