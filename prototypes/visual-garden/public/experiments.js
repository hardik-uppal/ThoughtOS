import { validateGraph, normalisePrefs } from './model.js';

export const EXPERIMENT_KEY = 'thoughtos.visual-garden.experiments.v1';
export const PREFS_KEY = 'thoughtos.visual-garden.prefs.v1';
export const BUILD_ID = 'desk-03';
export function validSnapshot(s) {
  return s && typeof s.id === 'string' && typeof s.title === 'string' && s.title.length <= 120 &&
    ['manual', 'auto', 'safety'].includes(s.kind) && typeof s.createdAt === 'string' &&
    s.payload?.version === 2 && validateGraph(s.payload.notes) &&
    (!s.payload.events || (Array.isArray(s.payload.events) && s.payload.events.length <= 200 &&
      s.payload.events.every(e => typeof e.action === 'string' && e.action.length <= 300 && typeof e.at === 'string')));
}
export function readExperiments(storage) {
  const raw = storage.getItem(EXPERIMENT_KEY);
  if (!raw) return [];
  const data = JSON.parse(raw);
  if (data.version !== 1 || !Array.isArray(data.snapshots) || data.snapshots.length > 90 || !data.snapshots.every(validSnapshot)) throw new Error('Saved experiments could not be read. Existing data was preserved.');
  return data.snapshots;
}
export function saveExperiment(storage, { title, kind = 'manual', notes, prefs, events = [] }) {
  const saved = readExperiments(storage);
  if (kind === 'manual' && saved.filter(s => s.kind === 'manual').length >= 50) throw new Error('50 named snapshots saved. Delete one before saving another.');
  const snapshot = { id: crypto.randomUUID(), title: title.trim().slice(0, 120) || 'Untitled experiment', kind, createdAt: new Date().toISOString(),
    payload: { version: 2, buildId: BUILD_ID, notes: structuredClone(notes), prefs: normalisePrefs(prefs), events: events.slice(-200) } };
  if (!validSnapshot(snapshot)) throw new Error('Invalid snapshot; nothing was saved.');
  const next = [snapshot, ...saved];
  for (const type of ['auto', 'safety']) {
    let count = 0;
    for (let i = 0; i < next.length;) {
      if (next[i].kind === type && ++count > 20) next.splice(i, 1); else i++;
    }
  }
  // One atomic write: quota failures cannot leave a partial snapshot or evict old ones.
  storage.setItem(EXPERIMENT_KEY, JSON.stringify({ version: 1, snapshots: next }));
  return snapshot;
}
export function deleteExperiment(storage, id) {
  const snapshots = readExperiments(storage).filter(s => s.id !== id);
  storage.setItem(EXPERIMENT_KEY, JSON.stringify({ version: 1, snapshots }));
}
