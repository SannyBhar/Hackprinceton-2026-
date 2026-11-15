import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import type { Cell, Heading, Puzzle, PuzzleListItem, Snapshot } from '../api/types';
import { sameCell } from '../api/types';
import { Board, type PaintPhase } from '../board/Board';
import { referenceSolution, turnRight } from '../board/solve';
import { BoardCard, Blocks, Card, ErrorBox, TwoCol, fmtCell, useAction } from './common';

type Tool = 'path' | 'start' | 'scenery' | 'erase';
const TOOLS: { id: Tool; icon: string; label: string; hint: string }[] = [
  { id: 'path', icon: '✎', label: 'Path', hint: 'Drag from the start (or the end of the path) through neighbouring cells. Drag back one cell to undo it; hold Shift to step back as a deliberate revisit. Click any path cell to redraw from there.' },
  { id: 'start', icon: '◎', label: 'Start', hint: 'Click a cell to place the rover start. Click the start again to rotate its heading.' },
  { id: 'scenery', icon: '▲', label: 'Scenery', hint: 'Click or drag to add/remove decorative rocks. Scenery is visual only — it never affects grading.' },
  { id: 'erase', icon: '⌫', label: 'Erase', hint: 'Click a path cell to cut the path from that point; drag over rocks to clear them.' },
];
const ARROWS: Record<Heading, string> = { N: '↑', E: '→', S: '↓', W: '←' };

const adjacent = (a: Cell, b: Cell) => Math.abs(a.row - b.row) + Math.abs(a.col - b.col) === 1;
const strip = ({ builtin: _b, edited: _e, ...p }: PuzzleListItem | Puzzle & { builtin?: boolean; edited?: boolean }): Puzzle => p;
const withGoal = (p: Puzzle): Puzzle => ({
  ...p, goalCell: p.targetEntries.length ? p.targetEntries[p.targetEntries.length - 1] : p.startCell,
});
const slug = (s: string) => (s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'puzzle').slice(0, 40);

function blankPuzzle(): Puzzle {
  return {
    id: `puzzle-${Date.now().toString(36)}`, version: 1, name: 'Untitled puzzle',
    rows: 7, cols: 7, startCell: { row: 6, col: 3 }, startHeading: 'N', goalCell: { row: 6, col: 3 },
    targetEntries: [], sceneryCells: [],
  };
}

export function PuzzleEditor({ snap, onUse }: { snap: Snapshot; onUse: () => void }) {
  const { run, error, setError, busy } = useAction();
  const [list, setList] = useState<PuzzleListItem[]>([]);
  const [selectedId, setSelectedId] = useState(snap.puzzle.id);
  const [draft, setDraft] = useState<Puzzle>(snap.puzzle);
  const [dirty, setDirty] = useState(false);
  const [tool, setTool] = useState<Tool>('path');
  const [notice, setNotice] = useState<string | null>(null);
  const history = useRef<Puzzle[]>([]);
  const shift = useRef(false);
  const paintMode = useRef<'add' | 'remove'>('add');

  const refresh = useCallback(() => api.puzzles().then(setList).catch(() => {}), []);
  useEffect(() => { refresh(); }, [refresh, snap.puzzle.id, snap.puzzle.version]);
  // Keep the active puzzle's draft in sync with the server when not editing it.
  useEffect(() => {
    if (!dirty && selectedId === snap.puzzle.id) setDraft(snap.puzzle);
  }, [snap.puzzle, dirty, selectedId]);

  const isActive = draft.id === snap.puzzle.id;
  const locked = snap.state === 'RUNNING' || snap.state === 'RECORDING';
  const route = draft.targetEntries;
  const last = route.length ? route[route.length - 1] : draft.startCell;

  // Latest draft for pointer handlers: several pointermoves can fire between renders.
  const draftRef = useRef(draft);
  draftRef.current = draft;

  const commit = (next: Puzzle, snapshot = true) => {
    if (snapshot) history.current = [...history.current.slice(-80), draftRef.current];
    draftRef.current = withGoal(next);
    setDraft(draftRef.current);
    setDirty(true);
    setError(null);
  };
  const undo = () => {
    const prev = history.current.pop();
    if (prev) { setDraft(prev); setDirty(true); }
  };

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      shift.current = e.shiftKey;
      const t = e.target as HTMLElement;
      if (t.tagName === 'INPUT' || t.tagName === 'SELECT') return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); }
      const k = { p: 'path', s: 'start', r: 'scenery', e: 'erase' }[e.key.toLowerCase()] as Tool | undefined;
      if (k && !e.metaKey && !e.ctrlKey) setTool(k);
    };
    const up = (e: KeyboardEvent) => { shift.current = e.shiftKey; };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  });

  // ------------------------------------------------------------------ painting
  const onPaint = (c: Cell, phase: PaintPhase) => {
    // 'end' is treated like a final 'move' so a fast stroke's last jump isn't lost.
    if (phase === 'end' && tool !== 'path' && tool !== 'scenery' && tool !== 'erase') return;
    const draft = draftRef.current;
    const route = draft.targetEntries;
    const last = route.length ? route[route.length - 1] : draft.startCell;
    const isStart = phase === 'start';
    const scenery = draft.sceneryCells;
    const noScenery = (cells: Cell[]) => scenery.filter((s) => !cells.some((c2) => sameCell(s, c2)));

    if (tool === 'start') {
      if (!isStart) return;
      if (sameCell(c, draft.startCell)) commit({ ...draft, startHeading: turnRight(draft.startHeading) });
      else commit({ ...draft, startCell: c, targetEntries: [], sceneryCells: noScenery([c]) });
      return;
    }

    if (tool === 'scenery' || (tool === 'erase' && !route.some((r) => sameCell(r, c)))) {
      const onRoute = sameCell(c, draft.startCell) || route.some((r) => sameCell(r, c));
      const has = scenery.some((s) => sameCell(s, c));
      if (isStart) paintMode.current = tool === 'erase' ? 'remove' : has ? 'remove' : 'add';
      if (paintMode.current === 'add' && !has && !onRoute) commit({ ...draft, sceneryCells: [...scenery, c] }, isStart);
      else if (paintMode.current === 'remove' && has) commit({ ...draft, sceneryCells: noScenery([c]) }, isStart);
      return;
    }

    if (tool === 'erase') {
      if (!isStart) return;
      const i = route.findIndex((r) => sameCell(r, c));
      commit({ ...draft, targetEntries: route.slice(0, i) });
      return;
    }

    // ---- path tool
    if (isStart) {
      if (sameCell(c, last)) { history.current = [...history.current.slice(-80), draft]; return; }
      if (adjacent(c, last)) { commit({ ...draft, targetEntries: [...route, c], sceneryCells: noScenery([c]) }); return; }
      if (sameCell(c, draft.startCell)) { commit({ ...draft, targetEntries: [] }); return; }
      const i = route.map((r, k) => (sameCell(r, c) ? k : -1)).filter((k) => k >= 0).pop();
      if (i !== undefined) { commit({ ...draft, targetEntries: route.slice(0, i + 1) }); return; }
      setNotice(`Start drawing from the end of the path ${fmtCell(last)} — it's outlined in blue.`);
      return;
    }
    // drag move: extend along straight lines, backtrack = undo unless Shift (revisit)
    const prev = route.length >= 2 ? route[route.length - 2] : route.length === 1 ? draft.startCell : null;
    if (prev && sameCell(c, prev) && !shift.current) {
      commit({ ...draft, targetEntries: route.slice(0, -1) }, false);
      return;
    }
    const steps: Cell[] = [];
    if (c.row === last.row || c.col === last.col) {
      const dr = Math.sign(c.row - last.row), dc = Math.sign(c.col - last.col);
      let cur = last;
      while (!sameCell(cur, c)) { cur = { row: cur.row + dr, col: cur.col + dc }; steps.push(cur); }
    }
    if (steps.length) commit({ ...draft, targetEntries: [...route, ...steps], sceneryCells: noScenery(steps) }, false);
  };

  // ------------------------------------------------------------------ board size
  const resize = (rows: number, cols: number) => {
    rows = Math.max(2, Math.min(12, rows));
    cols = Math.max(2, Math.min(12, cols));
    const inb = (c: Cell) => c.row < rows && c.col < cols;
    const start = inb(draft.startCell) ? draft.startCell : { row: rows - 1, col: 0 };
    const cut = draft.targetEntries.findIndex((c) => !inb(c));
    commit({
      ...draft, rows, cols, startCell: start,
      targetEntries: !inb(draft.startCell) ? [] : cut === -1 ? draft.targetEntries : draft.targetEntries.slice(0, cut),
      sceneryCells: draft.sceneryCells.filter(inb),
    });
  };

  // ------------------------------------------------------------------ library
  const select = (p: Puzzle) => {
    if (dirty && !window.confirm('Discard unsaved changes to this puzzle?')) return;
    history.current = [];
    setSelectedId(p.id);
    setDraft(strip(p));
    setDirty(false);
    setError(null);
    setNotice(null);
  };

  const validate = (): string | null => {
    if (!draft.name.trim()) return 'Give the puzzle a name.';
    if (!draft.targetEntries.length) return 'Draw a route of at least one cell from the start.';
    return null;
  };

  const saveAndUse = () => run(async () => {
    const v = validate(); if (v) throw new Error(v);
    await api.savePuzzle(strip(draft));
    setDirty(false); setSelectedId(draft.id);
    await refresh();
    setNotice('Saved and loaded onto the board.');
  });
  const saveOnly = () => run(async () => {
    const v = validate(); if (v) throw new Error(v);
    if (isActive) await api.savePuzzle(strip(draft)); else await api.savePuzzleOnly(strip(draft));
    setDirty(false); setSelectedId(draft.id);
    await refresh();
    setNotice('Saved to the library.');
  });
  const saveCopy = () => run(async () => {
    const v = validate(); if (v) throw new Error(v);
    const copy = { ...strip(draft), id: `${slug(draft.name)}-${Date.now().toString(36)}`, version: 1, name: `${draft.name} (copy)` };
    await api.savePuzzleOnly(copy);
    setDraft(copy); setSelectedId(copy.id); setDirty(false);
    await refresh();
    setNotice('Saved a copy.');
  });
  const remove = (p: PuzzleListItem) => run(async () => {
    const verb = p.builtin ? 'Revert your edits to' : 'Delete';
    if (!window.confirm(`${verb} “${p.name}”?`)) return;
    const r = await api.deletePuzzle(p.id);
    const fresh = await api.puzzles();
    setList(fresh);
    if (r.result === 'deleted') { select(fresh.find((x) => x.id === snap.puzzle.id) ?? fresh[0]); }
    else { const orig = fresh.find((x) => x.id === p.id); if (orig) { setDraft(strip(orig)); setDirty(false); } }
    setNotice(r.result === 'deleted' ? 'Puzzle deleted.' : 'Reverted to the original example.');
  });
  const newPuzzle = () => {
    if (dirty && !window.confirm('Discard unsaved changes to this puzzle?')) return;
    const p = blankPuzzle();
    history.current = [];
    setDraft(p); setSelectedId(p.id); setDirty(true); setTool('path');
    setNotice('New puzzle — set the start, then drag out the route.');
  };

  // ------------------------------------------------------------------ derived
  const solution = useMemo(() => referenceSolution(draft.startCell, draft.startHeading, route, snap.maxSteps),
    [draft.startCell, draft.startHeading, route, snap.maxSteps]);
  const turns = solution.filter((i) => i.op === 'LEFT' || i.op === 'RIGHT').length;
  const revisits = route.filter((c, i) => [draft.startCell, ...route.slice(0, i)].some((p) => sameCell(p, c))).length;
  const selectedItem = list.find((p) => p.id === draft.id);
  const toolInfo = TOOLS.find((t) => t.id === tool)!;
  const unsavedNew = !selectedItem;

  return (
    <TwoCol
      left={
        <>
          <Card title="Puzzle library" subtitle="Pick a puzzle to edit, or start a new one."
                actions={<button className="primary" onClick={newPuzzle}>+ New</button>}>
            <div className="library">
              {unsavedNew && (
                <div className="lib-item selected">
                  <div className="meta"><b>{draft.name}</b><span>not saved yet</span></div>
                  <span className="badge">draft</span>
                </div>
              )}
              {list.map((p) => (
                <button key={p.id} className={`lib-item ${p.id === selectedId ? 'selected' : ''}`} onClick={() => select(p)}>
                  <div className="mini-board"><Board puzzle={p} showIndices={false} showRobot={false} width="100%" height="auto" /></div>
                  <div className="meta">
                    <b>{p.name}</b>
                    <span>{p.rows}×{p.cols} · {p.targetEntries.length} steps · v{p.version}</span>
                  </div>
                  {p.id === snap.puzzle.id && <span className="badge active">on board</span>}
                  {p.builtin && <span className="badge">{p.edited ? 'example · edited' : 'example'}</span>}
                </button>
              ))}
            </div>
          </Card>

          <Card title="Details" subtitle={isActive ? 'This puzzle is on the board now.' : 'Not on the board yet.'}>
            <label className="field">Name
              <input value={draft.name} maxLength={60} onChange={(e) => commit({ ...draft, name: e.target.value })} />
            </label>
            <div className="row" style={{ gap: 18, alignItems: 'flex-end' }}>
              <div className="field">Rows
                <div className="stepper">
                  <button onClick={() => resize(draft.rows - 1, draft.cols)}>−</button><span>{draft.rows}</span>
                  <button onClick={() => resize(draft.rows + 1, draft.cols)}>+</button>
                </div>
              </div>
              <div className="field">Columns
                <div className="stepper">
                  <button onClick={() => resize(draft.rows, draft.cols - 1)}>−</button><span>{draft.cols}</span>
                  <button onClick={() => resize(draft.rows, draft.cols + 1)}>+</button>
                </div>
              </div>
              <div className="field">Start heading
                <div className="heading-pick">
                  <span /><HeadingBtn h="N" draft={draft} commit={commit} /><span />
                  <HeadingBtn h="W" draft={draft} commit={commit} />
                  <span className="muted small" style={{ display: 'grid', placeItems: 'center' }}>{draft.startHeading}</span>
                  <HeadingBtn h="E" draft={draft} commit={commit} />
                  <span /><HeadingBtn h="S" draft={draft} commit={commit} /><span />
                </div>
              </div>
            </div>
          </Card>

          <Card title="Draw" subtitle="Shortcuts: P path · S start · R rocks · E erase · ⌘/Ctrl+Z undo">
            <div className="tools">
              {TOOLS.map((t) => (
                <button key={t.id} className={`tool ${tool === t.id ? 'on' : ''}`} onClick={() => setTool(t.id)}>
                  <span className="ic">{t.icon}</span>{t.label}
                </button>
              ))}
            </div>
            <div className="note info">{toolInfo.hint}</div>
            <div className="row">
              <button onClick={undo} disabled={!history.current.length}>↶ Undo</button>
              <button onClick={() => commit({ ...draft, targetEntries: [] })} disabled={!route.length}>Clear path</button>
              <button onClick={() => commit({ ...draft, sceneryCells: [] })} disabled={!draft.sceneryCells.length}>Clear rocks</button>
            </div>
          </Card>

          <Card title="Route" subtitle={`Start ${fmtCell(draft.startCell)} facing ${draft.startHeading} → goal ${fmtCell(draft.goalCell)}`}>
            <div className="stats">
              <div className="stat"><b>{route.length}</b><span>cells to enter</span></div>
              <div className="stat"><b>{turns}</b><span>turns</span></div>
              <div className="stat"><b>{solution.length}</b><span>cards (ref.)</span></div>
            </div>
            {revisits > 0 && <div className="note info">Route revisits {revisits} cell{revisits > 1 ? 's' : ''} — revisits are graded by order, like every step.</div>}
            {route.length > 0 ? (
              <>
                <p className="muted small" style={{ margin: '8px 0 4px' }}>One card solution (reference for you — students may find others):</p>
                <Blocks program={solution} />
              </>
            ) : <p className="muted small">No route yet.</p>}
          </Card>

          <Card title="Save">
            {dirty && <div className="note warn">Unsaved changes.</div>}
            {notice && !dirty && <div className="note ok">{notice}</div>}
            {notice && dirty && <div className="note info">{notice}</div>}
            <ErrorBox error={error} />
            <div className="row">
              <button className="primary" disabled={busy || locked || (!dirty && isActive)} onClick={saveAndUse}>
                {isActive ? 'Save to board' : 'Save & use on board'}
              </button>
              <button disabled={busy || !dirty || (isActive && locked)} onClick={saveOnly}>Save</button>
              <button disabled={busy || !route.length} onClick={saveCopy}>Save as copy</button>
            </div>
            <div className="row">
              {isActive && !dirty && <button className="ghost" onClick={onUse}>Go to Program →</button>}
              <button className="ghost" disabled={!dirty} onClick={() => {
                const orig = list.find((p) => p.id === draft.id);
                if (orig) { setDraft(strip(orig)); setDirty(false); history.current = []; } else newPuzzle();
              }}>Discard changes</button>
              {selectedItem && (selectedItem.edited || !selectedItem.builtin) && !isActive && (
                <button className="ghost danger-text" onClick={() => remove(selectedItem)}>
                  {selectedItem.builtin ? 'Revert example' : 'Delete puzzle'}
                </button>
              )}
            </div>
            {locked && <p className="muted small">The board puzzle can't change while the rover is {snap.state.toLowerCase()}.</p>}
          </Card>
        </>
      }
      right={
        <BoardCard
          title={<>{draft.name}{dirty && <span className="badge" style={{ marginLeft: 8 }}>editing</span>}</>}
          extra={<span className="muted small">{toolInfo.icon} {toolInfo.label} tool</span>}
          footer={<p className="muted small" style={{ margin: 0 }}>
            Numbers show the order cells must be entered. The blue outline marks where the path continues.
          </p>}
        >
          <Board puzzle={draft} theme={snap.projection.theme} onPaint={onPaint}
                 highlight={tool === 'path' ? [last] : []} roverAtStart width="100%" height="auto" />
        </BoardCard>
      }
    />
  );
}

function HeadingBtn({ h, draft, commit }: { h: Heading; draft: Puzzle; commit: (p: Puzzle) => void }) {
  return (
    <button className={draft.startHeading === h ? 'selected' : ''} title={`Face ${h}`}
            onClick={() => commit({ ...draft, startHeading: h })}>{ARROWS[h]}</button>
  );
}
