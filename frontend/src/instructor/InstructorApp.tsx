import { openProjectionWindow } from '../projection/window';
export { openProjectionWindow } from '../projection/window';
import { useState } from 'react';
import { api } from '../api/client';
import { useSession } from '../api/useSession';
import { RoverIcon } from '../board/Rover';
import { LiveTab } from './LiveTab';
import { ProgramTab } from './ProgramTab';
import { PuzzleEditor } from './PuzzleEditor';
import { RecordingTab } from './RecordingTab';
import { SetupTab } from './SetupTab';

const TABS = [
  ['setup', '1', 'Setup'],
  ['puzzle', '2', 'Puzzles'],
  ['program', '3', 'Program'],
  ['live', '4', 'Run'],
  ['record', '◉', 'Record'],
] as const;
type Tab = (typeof TABS)[number][0];

export function InstructorApp() {
  const { snap, connected } = useSession();
  const [tab, setTab] = useState<Tab>('puzzle');

  if (!snap) {
    return <div className="loading">Connecting to the Grassroot backend… (is it running on :8000?)</div>;
  }
  const moving = snap.state === 'RUNNING' || snap.state === 'RECORDING';

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark"><RoverIcon size={30} /></div>
          <div>
            <h1>Grassroot</h1>
            <small>{snap.puzzle.name}</small>
          </div>
        </div>
        <span className={`state state-${snap.state}`}>{snap.state.replace('_', ' ')}</span>
        <span className="spacer" />
        <span className="chip"><span className={`dot ${snap.robot.connected ? 'ok' : 'bad'}`} />
          Rover · {snap.robot.adapter}</span>
        <span className="chip"><span className={`dot ${connected ? 'ok' : 'bad'}`} />{connected ? 'Live' : 'Reconnecting'}</span>
        <button onClick={openProjectionWindow}>Open projection ↗</button>
        {moving && <button className="stop" onClick={() => api.stop()}>■ STOP</button>}
      </header>
      <nav className="tabs">
        {TABS.map(([id, num, label]) => (
          <button key={id} className={tab === id ? 'tab active' : 'tab'} onClick={() => setTab(id)}>
            <span className="num">{num}</span>{label}
          </button>
        ))}
      </nav>
      <main>
        {tab === 'setup' && <SetupTab snap={snap} />}
        {tab === 'puzzle' && <PuzzleEditor snap={snap} onUse={() => setTab('program')} />}
        {tab === 'program' && <ProgramTab snap={snap} onRun={() => setTab('live')} />}
        {tab === 'live' && <LiveTab snap={snap} />}
        {tab === 'record' && <RecordingTab snap={snap} />}
      </main>
    </div>
  );
}
