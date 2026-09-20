export const STORAGE_KEY = 'thoughtos.visual-garden.v1';
export const TOPICS = ['Making things', 'Wardrub', 'Learning', 'Everyday'];
const rows = [
  ['A place to wander', 'Making things', ['thoughtos', 'connections'], 'What if a notes app felt less like a filing cabinet and more like a room you wanted to spend time in?\n\nLeave room for the unfinished thought. The detour is part of the work.', ['n2', 'n3', 'n4', 'n5'], 'A little unfinished is a good thing.'],
  ['The notebook test', 'Making things', ['thoughtos', 'design'], 'Open a notebook at a random page. A crossed-out sentence can tell you more than a polished summary.\n\nKeep the rough edges, but make the important words easy to read.', ['n3', 'n12'], 'Keep the fingerprints.'],
  ['Small notes, big connections', 'Learning', ['connections', 'zettelkasten'], 'One idea per card. Give it a name that says something, not just a category.\n\nA link should answer: why did these two thoughts make me think of each other?', ['n4', 'n13', 'n19'], 'A card is a beginning, not a box.'],
  ['Follow the interesting edge', 'Making things', ['connections', 'design'], 'A graph should start with one thought and unfold gently. Twenty useful neighbours are better than a thousand tiny dots.\n\nAlways leave a breadcrumb home.', ['n5', 'n13'], 'Less galaxy. More constellation.'],
  ['A cloud of things on my mind', 'Making things', ['thoughtos', 'discovery'], 'Words can be doorways. Let a topic grow with the number of notes it touches.\n\nClick a word, find a handful of notes, and see what catches your eye.', ['n19'], 'What keeps coming back?'],
  ['Clothes, not catalogues', 'Wardrub', ['wardrub', 'capture'], 'A wardrobe begins with the clothes already in your room. Capture should work on a hanger, on a bed, and in imperfect light.\n\nMake the first useful result feel effortless.', ['n7', 'n8', 'n9'], 'Start with what you own.'],
  ['Preserve the little details', 'Wardrub', ['wardrub', 'fidelity'], 'The stripe, the button, the tiny embroidered mark: these make a garment yours.\n\nA cleaner image is not better if it quietly changes the clothing.', ['n8', 'n10'], 'Clean up the image, not the identity.'],
  ['Try the simpler model first', 'Wardrub', ['efficiency', 'experiments'], 'Could a good mask and a quiet background be enough?\n\nCompare segmentation with generative editing before deciding every photo needs a diffusion model.', ['n10', 'n11', 'n16'], 'Subtract before you generate.'],
  ['One garment, four photographs', 'Wardrub', ['capture', 'data'], 'Pilot collection idea: photograph the same garment on a hanger, flat on a table, in clutter, and against a clean background.\n\nKeep related views in the same dataset split. Consent and source records travel with each photo.', ['n10', 'n11'], 'Variety without losing provenance.'],
  ['What does better actually mean?', 'Learning', ['experiments', 'fidelity'], 'Write down the decision before running the experiment: faster, more faithful, or less likely to fail?\n\nCount accepted outputs, not just generated images.', ['n11', 'n16', 'n20'], 'Make the trade-off visible.'],
  ['A tiny, trustworthy benchmark', 'Learning', ['data', 'experiments'], 'Start with two smoke tests and a small frozen evaluation set. Include the awkward cases.\n\nA benchmark is a promise not to move the goalposts halfway through.', ['n16'], 'Small enough to run. Good enough to trust.'],
  ['Margins are thinking space', 'Making things', ['design', 'notebooks'], 'Leave somewhere to put the thought that does not quite fit. Margins, sticky notes, little arrows.\n\nWhitespace can be an invitation rather than an absence.', ['n14', 'n18'], 'Not every pixel needs a job.'],
  ['The surprising neighbour', 'Everyday', ['connections', 'discovery'], 'A recipe and a research paper can share a useful idea: change one ingredient at a time.\n\nThe most interesting connection often crosses a folder boundary.', ['n14', 'n16', 'n19'], 'Let the folders leak a little.'],
  ['Coffee and a blank page', 'Everyday', ['rituals', 'notebooks'], 'Ten quiet minutes. One page. No requirement to be useful.\n\nWrite the thing you noticed before deciding what it belongs to.', ['n15', 'n17', 'n18'], 'Notice first. Organise later.'],
  ['Walk without a podcast', 'Everyday', ['rituals', 'attention'], 'Give the mind an empty stretch of pavement. Sometimes a thought needs less input, not a better prompt.\n\nCapture the one thing that is still there when you get home.', ['n17', 'n20'], 'Space to hear yourself think.'],
  ['Change one ingredient', 'Learning', ['experiments', 'learning'], 'Keep a baseline. Change one thing. Write down what surprised you.\n\nThis applies equally well to a model configuration, a recipe, and a morning routine.', ['n20'], 'Curiosity with a control group.'],
  ['A pocket for loose thoughts', 'Everyday', ['capture', 'attention'], 'Capture should not demand a title, a folder, a tag, and a decision.\n\nMake a little inbox for the sentences that arrive before their context does.', ['n18', 'n19'], 'Catch it before it disappears.'],
  ['Make room for unfinished work', 'Making things', ['design', 'rituals'], 'A rough note is not a failed document. It is a thought still becoming something.\n\nMake revisiting feel inviting rather than overdue.', ['n20'], 'A garden, not a queue.'],
  ['Rediscovery, not just search', 'Learning', ['discovery', 'thoughtos'], 'Search helps when you know what you want. Browsing helps when you do not.\n\nOffer a topic, a nearby note, or a small surprise. Never hide the way back.', ['n20'], 'Find the thing you forgot to look for.'],
  ['Leave a trail for tomorrow', 'Everyday', ['learning', 'attention'], 'At the end of a session, leave one sentence: here is what I was wondering.\n\nTomorrow needs a foothold, not a perfect summary.', [], 'A note to your future self.'],
];
export function freshNotes() {
  return rows.map(([title, topic, tags, body, links, aside], i) => ({
    id: `n${i + 1}`, title, topic, tags: [...tags], body, links: [...links], aside,
    createdAt: '2026-09-01T10:00:00.000Z',
  }));
}
export function validateNotes(notes) {
  if (!Array.isArray(notes) || notes.length < 1 || notes.length > 500) return false;
  const ids = new Set(notes.map(n => n?.id));
  return ids.size === notes.length && notes.every(n => n &&
    typeof n.id === 'string' && n.id.length > 0 && n.id.length < 100 &&
    typeof n.title === 'string' && n.title.trim().length > 0 && n.title.length <= 120 &&
    typeof n.body === 'string' && n.body.length <= 20000 && TOPICS.includes(n.topic) &&
    typeof n.aside === 'string' && typeof n.createdAt === 'string' &&
    Array.isArray(n.tags) && n.tags.length <= 12 && n.tags.every(t => typeof t === 'string' && t.length <= 40) &&
    Array.isArray(n.links) && n.links.every(id => ids.has(id) && id !== n.id));
}
export function related(notes, id) {
  const note = notes.find(n => n.id === id);
  return note ? notes.filter(n => n.id !== id && (note.links.includes(n.id) || n.links.includes(id))) : [];
}
export function parseSearch(query = '') {
  const tags = [];
  const text = query.replace(/(?:^|\s)(?:#|tag:)([\p{L}\p{N}_-]+)/gu, (_, tag) => { tags.push(tag.toLowerCase()); return ' '; }).trim().toLowerCase();
  return { tags, text, words: text.split(/\s+/).filter(Boolean) };
}
export function filtered(notes, { query = '', topic = '', tag = '' } = {}) {
  const search = parseSearch(query);
  return notes.filter(n => {
    const tags = n.tags.map(t => t.toLowerCase());
    const haystack = `${n.title} ${n.body} ${tags.join(' ')}`.toLowerCase();
    return (!topic || n.topic === topic) && (!tag || tags.includes(tag.toLowerCase())) &&
      search.tags.every(t => tags.includes(t)) && search.words.every(word => haystack.includes(word));
  });
}
export const DEFAULT_PREFS = { compose: 'freeform', density: 'compact', semantic: true, arrange: 'meaning' };
export function normalisePrefs(p = {}) {
  return {
    compose: p.compose === 'structured' ? 'structured' : 'freeform',
    density: p.density === 'comfortable' ? 'comfortable' : 'compact',
    semantic: typeof p.semantic === 'boolean' ? p.semantic : true,
    arrange: ['meaning', 'collection', 'recent'].includes(p.arrange) ? p.arrange : 'meaning',
  };
}
const STOP_WORDS = new Set('a an the and or but for to of in on at by with from as is are was were be been being it its this that these those i we you they he she my our your their me us them have has had do does did can could would should will just very more most less some any all not no also into about through how what when where why who maybe need want feel think use using used then than like so if there here new'.split(' '));
export function deriveMetadata(body, notes = []) {
  const plain = body.replace(/^\s*[-#*>\d.)]+\s*/gm, '').trim();
  const first = plain.split(/\n|(?<=[.!?])\s/)[0] || '';
  const title = first.length > 72 ? first.slice(0, 69).replace(/\s+\S*$/, '') + '…' : first;
  const words = plain.toLowerCase().match(/[\p{L}][\p{L}\p{N}-]*/gu) || [];
  const wordSet = new Set(words);
  const known = topicsCloud(notes).map(([t]) => t).filter(t => t.split(/[\s-]+/).every(w => wordSet.has(w)));
  const counts = new Map();
  for (const word of words) if (word.length > 3 && !STOP_WORDS.has(word)) counts.set(word, (counts.get(word) || 0) + 1);
  const keywords = [...counts].sort((a,b) => b[1] - a[1]).map(([w]) => w);
  return { title, tags: [...new Set([...known, ...keywords])].slice(0, 4) };
}
export function topicsCloud(notes) {
  const counts = new Map();
  for (const note of notes) for (const tag of new Set(note.tags)) counts.set(tag, (counts.get(tag) || 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}
export function addLink(notes, source, target) {
  if (source === target || !notes.some(n => n.id === source) || !notes.some(n => n.id === target)) return notes;
  if (related(notes, source).some(n => n.id === target)) return notes;
  return notes.map(n => n.id === source ? { ...n, links: [...n.links, target] } : n);
}
// Shared tags suggest a direction; they never silently create a link.
export function suggestions(notes, id, limit = 6) {
  const source = notes.find(n => n.id === id);
  if (!source) return [];
  const connected = new Set(related(notes, id).map(n => n.id));
  return notes.filter(n => n.id !== id && !connected.has(n.id))
    .map(note => ({ note, tags: note.tags.filter(t => source.tags.includes(t)) }))
    .filter(item => item.tags.length)
    .sort((a, b) => b.tags.length - a.tags.length || a.note.title.localeCompare(b.note.title))
    .slice(0, limit);
}
export function removeLink(notes, source, target) {
  return notes.map(n => n.id === source || n.id === target
    ? { ...n, links: n.links.filter(id => id !== (n.id === source ? target : source)) } : n);
}
