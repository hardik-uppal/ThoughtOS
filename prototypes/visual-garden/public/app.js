import { STORAGE_KEY, TOPICS, freshNotes, validateNotes, related, filtered, topicsCloud, addLink, removeLink, suggestions } from './model.js';

const $ = s => document.querySelector(s);
const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
document.querySelectorAll('[data-key]').forEach(el => { el.textContent = `${isMac ? '⌘' : 'Ctrl'} ${el.dataset.key}`; });
let notes = freshNotes();
let storageBlocked = false;
try {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) {
    const parsed = JSON.parse(saved);
    if (parsed.version !== 1 || !validateNotes(parsed.notes)) throw new Error('Invalid saved garden');
    notes = parsed.notes;
  }
} catch {
  storageBlocked = true;
  $('#storage-warning').hidden = false;
  $('#storage-warning').textContent = 'Saved browser data could not be loaded. Your stored data has not been overwritten. Demo edits are temporary until you reset.';
}
const state = { view: 'desk', query: '', topic: '', tag: '', selected: notes[0].id, history: [notes[0].id], cursor: 0 };
const undoStack = [];
let editing = null, editingTags = [], pendingLinkSource = null, picker = null, toastTimer;
const color = note => ['peach', 'sage', 'butter', 'lavender'][TOPICS.indexOf(note.topic)];
const visible = () => filtered(notes, state);
const selected = () => notes.find(n => n.id === state.selected);
const number = note => String(notes.findIndex(n => n.id === note.id) + 1).padStart(2, '0');
function toast(message) {
  $('#toast').textContent = message; $('#toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4500);
}
function save() {
  if (storageBlocked) { toast('Changed for this visit only; browser storage is unavailable.'); return; }
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, notes })); }
  catch {
    storageBlocked = true; $('#storage-warning').hidden = false;
    $('#storage-warning').textContent = 'Browser storage is unavailable or full. Changes will not survive a reload.';
    toast('Could not save to browser storage; changes are temporary.');
  }
}
function commit(next, message) {
  undoStack.push(structuredClone(notes)); if (undoStack.length > 30) undoStack.shift();
  notes = next; toast(message); save(); render();
}
function focusThought() {
  const target = state.view === 'chain' ? $('.chain-focus h2') : $('#inspector h2');
  target?.focus({ preventScroll: true });
  if (innerWidth < 1100 && state.view !== 'chain') $('#inspector').scrollIntoView({ block: 'start' });
}
function selectNote(id, { chain = false, focus = true } = {}) {
  if (!notes.some(n => n.id === id)) return;
  if (chain) state.view = 'chain';
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
  state.cursor = index; state.selected = state.history[index]; render(); focusThought();
}
function setFilter(kind, value) { state[kind] = state[kind] === value ? '' : value; state.view = 'desk'; render(); }
function clearFilters() { state.query = ''; state.topic = ''; state.tag = ''; $('#search').value = ''; render(); }
function renderSidebar() {
  $('#collections').innerHTML = `<button data-topic="" class="collection ${!state.topic ? 'active' : ''}" aria-pressed="${!state.topic}"><span><i>◈</i> All thoughts</span><small>${notes.length}</small></button>` + TOPICS.map((topic, i) => `<button data-topic="${esc(topic)}" class="collection ${state.topic === topic ? 'active' : ''}" aria-pressed="${state.topic === topic}"><span><i class="topic-dot ${['peach', 'sage', 'butter', 'lavender'][i]}"></i>${esc(topic)}</span><small>${notes.filter(n => n.topic === topic).length}</small></button>`).join('');
  $('#cloud').innerHTML = topicsCloud(notes).slice(0, 16).map(([tag, count]) => `<button data-tag="${esc(tag)}" class="cloud-word ${state.tag === tag ? 'active' : ''}" style="--word-size:${12 + count * 2}px" aria-pressed="${state.tag === tag}" title="${count} notes tagged ${esc(tag)}">${esc(tag)}</button>`).join('');
  $('#corner-label').textContent = state.view === 'chain' ? 'Following a thought' : state.topic || 'All thoughts';
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
function branchCard(note) {
  return `<button class="branch-card ${color(note)}" data-hop="${esc(note.id)}"><span class="card-top">${esc(note.topic)} <span>↔ LINKED</span></span><strong>${esc(note.title)}</strong><span class="branch-excerpt">${esc(note.body.slice(0, 85))}${note.body.length > 85 ? '…' : ''}</span><span class="branch-follow">Follow this branch →</span></button>`;
}
function renderChain() {
  const note = selected(), links = related(notes, note.id), split = Math.ceil(links.length / 2), nearby = suggestions(notes, note.id);
  return `<div class="chain-heading"><div><span class="eyebrow">FOLLOW ANY DIRECTION</span><h2>One thought. ${links.length} ${links.length === 1 ? 'way' : 'ways'} onward.</h2><p>Every solid link works both ways. Click a neighbour to keep going.</p></div><button id="all-cards" class="text-button">← All cards</button></div><div class="chain-board"><div class="branch-column">${links.slice(0, split).map(branchCard).join('')}</div><article class="chain-focus ${color(note)}"><span class="focus-label">YOU ARE HERE</span><h2 tabindex="-1">${esc(note.title)}</h2><p>${esc(note.body.split('\n\n')[0])}</p><div class="focus-tags">${note.tags.map(t => `<button data-tag="${esc(t)}">#${esc(t)}</button>`).join('')}</div><button data-edit="${esc(note.id)}" class="focus-edit">Edit this thought <kbd>E</kbd></button><button data-connect="${esc(note.id)}" class="connect-primary">＋ Connect another thought</button></article><div class="branch-column">${links.slice(split).map(branchCard).join('')}</div></div>${!links.length ? '<p class="chain-empty">This thought has no connections yet. Use “Connect another thought” to start its chain.</p>' : ''}<section class="nearby"><div class="nearby-heading"><h3>Another angle?</h3><span>SHARED TAGS · NOT LINKED</span></div><p>These thoughts share a tag. Explore one, or deliberately connect it.</p>${nearby.length ? `<div class="nearby-grid">${nearby.map(({ note: n, tags }) => `<article class="nearby-card"><button data-hop="${esc(n.id)}"><strong>${esc(n.title)}</strong><small>Shares ${tags.map(t => `#${esc(t)}`).join(', ')}</small></button><button class="suggest-connect" data-suggest-connect="${esc(n.id)}" aria-label="Connect to ${esc(n.title)}">＋ Connect</button></article>`).join('')}</div>` : '<p class="small-muted">No unlinked thoughts share these tags yet. Add a tag or find a thought to connect.</p>'}</section>`;
}
function renderInspector() {
  const note = selected(), links = related(notes, note.id);
  const outside = state.view !== 'chain' && !visible().some(n => n.id === note.id);
  $('#inspector').innerHTML = `<div class="inspector-top"><span>OPEN THOUGHT</span><small>DEMO / ${number(note)}</small></div><div class="inspector-toolbar"><button data-edit="${esc(note.id)}">✎ Edit note <kbd>E</kbd></button><button data-tags="${esc(note.id)}"># Tags <kbd>T</kbd></button></div><div class="inspector-paper ${color(note)}"><div class="card-top"><span>${esc(note.topic)}</span></div><h2 tabindex="-1">${esc(note.title)}</h2><div class="note-body">${note.body.split('\n\n').map(p => `<p>${esc(p)}</p>`).join('')}</div><div class="note-tags">${note.tags.map(t => `<button data-tag="${esc(t)}" title="Filter desk by ${esc(t)}">#${esc(t)}</button>`).join('')}<button class="tag-add" data-tags="${esc(note.id)}">＋ Add tag</button></div></div>${outside ? '<p class="outside-filter">This open thought is outside the desk filter. <button id="reveal-note">Clear filters to show it</button></p>' : ''}<section class="connections"><div class="connections-title"><h3>Connected thoughts <span>${links.length}</span></h3><button data-explore="${esc(note.id)}" class="text-button">Explore chain ↗</button></div><button class="connect-primary" id="connect-note" data-connect="${esc(note.id)}">＋ Connect a thought <kbd>C</kbd></button><p class="small-muted">Choose another card. A link appears on both.</p>${links.map(n => `<div class="connection-row"><button data-hop="${esc(n.id)}"><span class="thread-line">↔</span><span>${esc(n.title)}<small>${esc(n.topic)}</small></span><span>→</span></button><button class="unlink" data-unlink="${esc(n.id)}" aria-label="Remove connection to ${esc(n.title)}" title="Remove connection (undo available)">×</button></div>`).join('')}${!links.length ? '<p class="small-muted">No connections yet. Choose one above, or create a new connected thought.</p>' : ''}</section>`;
}
function renderWorkspace() {
  const items = visible();
  $('#workspace').className = `workspace view-${state.view}`;
  document.body.classList.toggle('exploring', state.view === 'chain');
  if (state.view === 'chain') $('#workspace').innerHTML = renderChain();
  else if (!items.length) $('#workspace').innerHTML = '<div class="empty-state"><span>✳</span><h2>A quiet corner.</h2><p>No notes match these filters. Try another word or show all cards.</p><button id="empty-clear" class="capture-button">Show all thoughts</button></div>';
  else if (state.view === 'desk') $('#workspace').innerHTML = `<div class="desk-grid">${items.map(card).join('')}</div>`;
  else $('#workspace').innerHTML = `<div class="notes-list">${items.map(n => `<div class="list-note ${n.id === state.selected ? 'active' : ''}"><button class="list-open" data-open="${esc(n.id)}"><span class="list-num">${number(n)}</span><span><strong>${esc(n.title)}</strong><small>${esc(n.topic)} · ${n.tags.map(t => `#${esc(t)}`).join(' ')}</small></span></button><button data-connect="${esc(n.id)}" class="text-button">＋ Connect</button><button data-explore="${esc(n.id)}" class="text-button">↔ ${related(notes, n.id).length} links</button></div>`).join('')}</div>`;
  $('#note-count').textContent = state.view === 'chain' ? `${related(notes, state.selected).length} connected thoughts · all collections` : `${items.length} of ${notes.length} demo thoughts`;
  $('#clear-filter').hidden = state.view === 'chain' || (!state.tag && !state.topic && !state.query);
  $('#clear-filter').textContent = `${state.tag ? `#${state.tag}` : state.topic || state.query} × Clear`;
  $('#view-hint').textContent = state.view === 'chain' ? 'Desk filters stay saved when you explore.' : '↑ ↓ ← → to move · Enter to open';
}
function render() {
  const focused = document.activeElement;
  const attr = ['data-open', 'data-connect', 'data-edit', 'data-tags', 'data-explore', 'data-topic', 'data-tag'].find(a => focused?.hasAttribute(a));
  const value = attr ? focused.getAttribute(attr) : null;
  const id = focused?.id;
  renderSidebar(); renderWorkspace(); renderInspector(); renderJourney();
  document.querySelectorAll('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === state.view)));
  $('#undo').disabled = !undoStack.length;
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
  $('#tag-input').value = ''; renderEditingTags();
}
function openEditor(id = null, { tags = false, linkFrom = null, title = '' } = {}) {
  editing = id; pendingLinkSource = linkFrom;
  const note = notes.find(n => n.id === id), form = $('#editor-form');
  $('#editor-heading').textContent = note ? 'Edit thought' : linkFrom ? 'New connected thought' : 'New thought';
  $('#editor-eyebrow').textContent = linkFrom ? `WILL CONNECT TO: ${notes.find(n => n.id === linkFrom)?.title}` : 'ONE IDEA IS ENOUGH';
  form.elements.title.value = note?.title || title; form.elements.body.value = note?.body || '';
  editingTags = [...(note?.tags || [])]; $('#tag-input').value = ''; renderEditingTags();
  form.elements.topic.innerHTML = TOPICS.map(t => `<option>${esc(t)}</option>`).join('');
  form.elements.topic.value = note?.topic || state.topic || TOPICS[0];
  $('#editor-dialog').showModal(); (tags ? $('#tag-input') : form.elements.title).focus();
}
function pickerItems() {
  const q = $('#picker-search').value.trim().replace(/^#/, '');
  const source = notes.find(n => n.id === picker.source);
  const connected = source ? new Set(related(notes, source.id).map(n => n.id)) : new Set();
  return filtered(notes, { query: q }).filter(n => picker.mode !== 'connect' || (n.id !== source?.id && !connected.has(n.id)))
    .sort((a, b) => (source ? b.tags.filter(t => source.tags.includes(t)).length - a.tags.filter(t => source.tags.includes(t)).length : 0));
}
function renderPicker() {
  const items = pickerItems(); picker.ids = items.map(n => n.id); picker.index = Math.min(Math.max(0, picker.index), Math.max(0, items.length - 1));
  const source = notes.find(n => n.id === picker.source);
  $('#picker-count').textContent = `${items.length} ${picker.mode === 'connect' ? 'available to connect' : 'thoughts found'}`;
  $('#picker-results').innerHTML = items.length ? items.map((n, i) => {
    const tags = source ? n.tags.filter(t => source.tags.includes(t)) : [];
    return `<button role="option" id="pick-${i}" aria-selected="${i === picker.index}" tabindex="-1" data-pick="${esc(n.id)}"><span class="pick-number ${color(n)}">${number(n)}</span><span class="pick-text"><strong>${esc(n.title)}</strong><small>${esc(n.topic)}${tags.length ? ` · shares ${tags.map(t => `#${esc(t)}`).join(', ')}` : ''}</small><span>${esc(n.body.slice(0, 100))}${n.body.length > 100 ? '…' : ''}</span></span><span class="pick-action">${picker.mode === 'connect' ? '＋ Connect' : 'Open ↗'}</span></button>`;
  }).join('') : '<p class="picker-empty">No matching thoughts. Try another word or write a new one.</p>';
  $('#picker-search').setAttribute('aria-activedescendant', items.length ? `pick-${picker.index}` : '');
}
function openPicker(mode = 'find', source = state.selected) {
  picker = { mode, source, index: 0, ids: [] };
  $('#picker-heading').textContent = mode === 'connect' ? 'Connect a thought' : 'Find a thought';
  $('#picker-eyebrow').textContent = mode === 'connect' ? 'ONE LINK. BOTH DIRECTIONS.' : 'SEARCH EVERY THOUGHT';
  $('#picker-context').textContent = mode === 'connect' ? `From “${notes.find(n => n.id === source).title}” → choose a thought below. Existing connections are excluded.` : 'Search across all collections, regardless of desk filters.';
  $('#picker-search').value = ''; $('#picker-feedback').textContent = '';
  $('#new-linked').hidden = mode !== 'connect'; renderPicker(); $('#picker-dialog').showModal(); $('#picker-search').focus();
}
function pickNote(id) {
  if (!picker?.ids.includes(id)) return;
  const { mode, source } = picker;
  $('#picker-dialog').close();
  if (mode === 'connect') {
    const target = notes.find(n => n.id === id);
    commit(addLink(notes, source, id), `Connected to “${target.title}”. The link is visible on both thoughts.`);
    selectNote(source);
  } else selectNote(id, { chain: true });
}
function undo() {
  if (!undoStack.length) return;
  notes = undoStack.pop();
  state.history = state.history.filter(id => notes.some(n => n.id === id));
  if (!state.history.length) state.history = [notes[0].id];
  state.cursor = Math.min(state.cursor, state.history.length - 1); state.selected = state.history[state.cursor];
  save(); render(); toast('Last edit undone.');
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
  if (b.dataset.close) $(`#${b.dataset.close}`).close();
  else if (b.dataset.view) { state.view = b.dataset.view; render(); }
  else if (b.dataset.open) selectNote(b.dataset.open);
  else if (b.dataset.hop) selectNote(b.dataset.hop, { chain: true });
  else if (b.dataset.explore) selectNote(b.dataset.explore, { chain: true });
  else if (b.dataset.connect) openPicker('connect', b.dataset.connect);
  else if (b.dataset.edit) openEditor(b.dataset.edit);
  else if (b.dataset.tags) openEditor(b.dataset.tags, { tags: true });
  else if (b.dataset.pick) pickNote(b.dataset.pick);
  else if (b.dataset.suggestConnect) commit(addLink(notes, state.selected, b.dataset.suggestConnect), 'Connected. This thought is now part of your chain.');
  else if (b.dataset.removeTag) { editingTags = editingTags.filter(t => t !== b.dataset.removeTag); renderEditingTags(); $('#tag-input').focus(); }
  else if (b.dataset.addTag) { addTags(b.dataset.addTag); $('#tag-input').focus(); }
  else if (b.hasAttribute('data-topic')) setFilter('topic', b.dataset.topic);
  else if (b.hasAttribute('data-tag')) setFilter('tag', b.dataset.tag);
  else if (b.hasAttribute('data-history')) goHistory(Number(b.dataset.history));
  else if (b.dataset.unlink) commit(removeLink(notes, state.selected, b.dataset.unlink), 'Connection removed from both notes. Undo is available.');
  else switch (b.id) {
    case 'new-note': openEditor(); break;
    case 'find-note': openPicker(); break;
    case 'help': $('#help-dialog').showModal(); break;
    case 'source-info': $('#sources-dialog').showModal(); break;
    case 'dismiss-guide': $('.quick-start').hidden = true; break;
    case 'clear-filter': case 'empty-clear': case 'reveal-note': clearFilters(); break;
    case 'all-cards': state.view = 'desk'; render(); break;
    case 'back': goHistory(state.cursor - 1); break;
    case 'forward': goHistory(state.cursor + 1); break;
    case 'add-tag': addTags($('#tag-input').value); $('#tag-input').focus(); break;
    case 'new-linked': { const source = picker.source, title = $('#picker-search').value.trim(); $('#picker-dialog').close(); openEditor(null, { linkFrom: source, title }); break; }
    case 'wander': { const pool = (state.view === 'chain' ? notes : visible()).filter(n => n.id !== state.selected); if (pool.length) selectNote(pool[Math.floor(Math.random() * pool.length)].id, { chain: true }); else toast('Clear the desk filters to find another thought.'); break; }
    case 'undo': undo(); break;
    case 'reset': {
      if (!confirm('Reset this browser’s demo notes? Your prototype edits will be removed. Real ThoughtOS notes are never touched.')) break;
      try { localStorage.removeItem(STORAGE_KEY); storageBlocked = false; $('#storage-warning').hidden = true; } catch { /* Retain in-memory mode. */ }
      notes = freshNotes(); undoStack.length = 0; state.view = 'desk'; state.selected = notes[0].id; state.history = [state.selected]; state.cursor = 0;
      clearFilters(); toast('Demo desk reset.'); break;
    }
  }
});
$('#search').addEventListener('input', event => { state.query = event.target.value; state.view = 'desk'; render(); });
$('#picker-search').addEventListener('input', () => { picker.index = 0; renderPicker(); });
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
  const data = new FormData(event.target), title = data.get('title').trim();
  if (!title) { event.target.elements.title.focus(); return; }
  const changes = { title, body: data.get('body').trim(), topic: data.get('topic'), tags: [...editingTags] };
  const uid = crypto.randomUUID?.() || [...crypto.getRandomValues(new Uint8Array(16))].map(b => b.toString(16).padStart(2, '0')).join('');
  const id = editing || `note-${uid}`;
  let next = editing ? notes.map(n => n.id === id ? { ...n, ...changes } : n) : [...notes, { id, ...changes, links: [], aside: '', createdAt: new Date().toISOString() }];
  if (pendingLinkSource) next = addLink(next, pendingLinkSource, id);
  if (!validateNotes(next)) { toast('This prototype supports up to 500 notes.'); return; }
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
  const typing = event.target.closest('input,textarea,select,[contenteditable="true"]');
  if (typing) return;
  if (event.altKey && ['ArrowLeft', 'ArrowRight'].includes(event.key)) { event.preventDefault(); goHistory(state.cursor + (event.key === 'ArrowLeft' ? -1 : 1)); return; }
  if (mod || event.altKey) return;
  const shortcuts = { '/': () => openPicker(), n: () => openEditor(), e: () => openEditor(state.selected), t: () => openEditor(state.selected, { tags: true }), c: () => openPicker('connect'), x: () => selectNote(state.selected, { chain: true }), '?': () => $('#help-dialog').showModal() };
  if (shortcuts[key]) { event.preventDefault(); shortcuts[key](); }
  else if (event.key.startsWith('Arrow') && $('#workspace').contains(event.target)) { event.preventDefault(); moveCard(event.key); }
});
render();
