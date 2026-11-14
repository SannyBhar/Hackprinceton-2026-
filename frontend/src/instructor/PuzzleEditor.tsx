import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Cell, Heading, Puzzle, Snapshot } from '../api/types';
import { sameCell } from '../api/types';
import { Board } from '../board/Board';
import { ErrorBox, TwoCol, fmtCell, useAction } from './common';

type Mode = 'start' | 'route' | 'scenery';
const adjacent = (a: Cell, b: Cell) => Math.abs(a.row - b.row) + Math.abs(a.col - b.col) === 1;

export function PuzzleEditor({ snap }: { snap: Snapshot }) {
  const { run, error, setError } = useAction();
  const [draft, setDraft] = useState<Puzzle>(snap.puzzle);
  const [dirty, setDirty] = useState(false);
  const [mode, setMode] = useState<Mode>('route');
  const [list, setList] = useState<Puzzle[]>([]);

  useEffect(() => { api.puzzles().then(setList).catch(() => {}); }, [snap.puzzle.id, snap.puzzle.version]);
  useEffect(() => { if (!dirty) setDraft(snap.puzzle); }, [snap.puzzle, dirty]);

  const update = (p: Partial<Puzzle>) => { setDraft((d) => ({ ...d, ...p })); setDirty(true); setError(null); };
  const route = draft.targetEntries;
  const last = route.length ? route[route.length - 1] : draft.startCell;

  const onCell = (c: Cell) => {
    if (mode === 'start') {
      update({ startCell: c, targetEntries: [], goalCell: c });
    } else if (mode === 'route') {
      if (route.length && sameCell(c, last)) {
        const r = route.slice(0, -1);
        update({ targetEntries: r, goalCell: r.length ? r[r.length - 1] : draft.startCell });
      } else if (adjacent(c, last)) {
        update({ targetEntries: [...route, c], goalCell: c });
      } else {
        setError(`Next route cell must be next to ${fmtCell(last)} (click the last cell to undo).`);
      }
    } else {
      const has = draft.sceneryCells.some((s) => sameCell(s, c));
      update({ sceneryCells: has ? draft.sceneryCells.filter((s) => !sameCell(s, c)) : [...draft.sceneryCells, c] });
    }
  };

  const resize = (rows: number, cols: number) => {
    const inb = (c: Cell) => c.row < rows && c.col < cols;
    const start = inb(draft.startCell) ? draft.startCell : { row: 0, col: 0 };
    const cut = draft.targetEntries.findIndex((c) => !inb(c));
    const r = cut === -1 ? draft.targetEntries : draft.targetEntries.slice(0, cut);
    update({ rows, cols, startCell: start, targetEntries: r, goalCell: r.length ? r[r.length - 1] : start,
             sceneryCells: draft.sceneryCells.filter(inb) });
  };

  const save = (asNew: boolean) => run(async () => {
    if (!draft.targetEntries.length) throw new Error('Draw at least one route cell.');
    const p = asNew
      ? { ...draft, id: `${draft.name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-${Date.now().toString(36)}`, version: 1 }
      : draft;
    await api.savePuzzle(p);
    setDirty(false);
  });

  const locked = snap.state === 'RUNNING' || snap.state === 'RECORDING';

  return (
    <TwoCol
      left={
        <>
          <h2>Puzzle</h2>
          <label className="field">Load
            <select value="" onChange={(e) => { const p = list.find((x) => x.id === e.target.value); if (p) run(() => api.savePuzzle(p)).then(() => setDirty(false)); }}>
              <option value="">— choose a saved puzzle —</option>
              {list.map((p) => <option key={p.id} value={p.id}>{p.name} (v{p.version})</option>)}
            </select>
          </label>
          <label className="field">Name <input value={draft.name} onChange={(e) => update({ name: e.target.value })} /></label>
          <div className="row">
            <label className="field">Rows <input type="number" min={2} max={20} value={draft.rows} onChange={(e) => resize(Number(e.target.value), draft.cols)} /></label>
            <label className="field">Cols <input type="number" min={2} max={20} value={draft.cols} onChange={(e) => resize(draft.rows, Number(e.target.value))} /></label>
            <label className="field">Start heading
              <select value={draft.startHeading} onChange={(e) => update({ startHeading: e.target.value as Heading })}>
                {['N', 'E', 'S', 'W'].map((h) => <option key={h}>{h}</option>)}
              </select>
            </label>
          </div>
          <h3>Click the board to…</h3>
          <div className="row">
            {(['start', 'route', 'scenery'] as Mode[]).map((m) => (
              <button key={m} className={mode === m ? 'primary' : ''} onClick={() => setMode(m)}>
                {m === 'start' ? 'Set start' : m === 'route' ? 'Draw ordered route' : 'Toggle scenery'}
              </button>
            ))}
          </div>
          <p className="muted small">
            The route is an <b>ordered</b> list of cell entries after leaving the start (revisits allowed).
            Goal = last route cell. Click the last cell again to undo.
          </p>
          <div className="row">
            <button onClick={() => update({ targetEntries: [], goalCell: draft.startCell })}>Clear route</button>
            <button disabled={!dirty} onClick={() => { setDraft(snap.puzzle); setDirty(false); }}>Discard edits</button>
          </div>
          <p><b>Start</b> {fmtCell(draft.startCell)} facing {draft.startHeading} · <b>Goal</b> {fmtCell(draft.goalCell)}</p>
          <ol className="route-list">{route.map((c, i) => <li key={i}>{fmtCell(c)}</li>)}</ol>
          <div className="row">
            <button className="primary" disabled={!dirty || locked} onClick={() => save(false)}>Save & load</button>
            <button disabled={locked} onClick={() => save(true)}>Save as new puzzle</button>
          </div>
          {locked && <p className="muted">Puzzle changes are blocked while {snap.state}.</p>}
          <ErrorBox error={error} />
        </>
      }
      right={
        <Board puzzle={draft} theme={snap.projection.theme} onCellClick={onCell}
               highlight={[last]} width="100%" height="auto" />
      }
    />
  );
}
