import { openProjectionWindow } from '../projection/window';
export { openProjectionWindow } from '../projection/window';
import { useState } from 'react';
import { useSession } from '../api/useSession';
import { LiveTab } from './LiveTab';
import { ProgramTab } from './ProgramTab';
import { PuzzleEditor } from './PuzzleEditor';
import { RecordingTab } from './RecordingTab';
import { SetupTab } from './SetupTab';

const TABS = [
  ['setup', 'Setup & Calibration'],
  ['puzzle', 'Puzzle Editor'],
  ['program', 'Program / Scan'],
  ['live', 'Live Attempt'],
  ['record', 'Joystick Recording'],
] as const;
type Tab = (typeof TABS)[number][0];

export function InstructorApp() {
  const { snap, connected } = useSession();
  const [tab, setTab] = useState<Tab>('setup');

  if (!snap) {
    return <div className="loading">Connecting to backend… (is <code>uvicorn</code> running on :8000?)</div>;
  }

  return (
    <div className="app">
      <header>
        <h1>Grassroot</h1>
        <span className={`state state-${snap.state}`}>{snap.state}</span>
        <span className="muted">{snap.puzzle.name} · v{snap.puzzle.version}</span>
        <span className="spacer" />
        <span className={`dot ${snap.robot.connected ? 'ok' : 'bad'}`} />
        <span className="muted">robot: {snap.robot.adapter}</span>
        <span className={`dot ${connected ? 'ok' : 'bad'}`} />
        <span className="muted">{connected ? 'live' : 'reconnecting'}</span>
        <button onClick={openProjectionWindow}>Open projection ↗</button>
      </header>
      <nav>
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? 'tab active' : 'tab'} onClick={() => setTab(id)}>{label}</button>
        ))}
      </nav>
      <main>
        {tab === 'setup' && <SetupTab snap={snap} />}
        {tab === 'puzzle' && <PuzzleEditor snap={snap} />}
        {tab === 'program' && <ProgramTab snap={snap} onRun={() => setTab('live')} />}
        {tab === 'live' && <LiveTab snap={snap} />}
        {tab === 'record' && <RecordingTab snap={snap} />}
      </main>
    </div>
  );
}
