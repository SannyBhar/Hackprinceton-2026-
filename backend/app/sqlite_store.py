"""SQLite repository with idempotent JSON import and normalized attempt evidence."""
import json
import sqlite3
import time
from pathlib import Path
from .storage import Storage
from .models import Puzzle, ProjectorCalibration
from .settings import FIXTURES

from .repository import RECORD_KINDS as KINDS


class SQLiteStorage(Storage):
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.path = data_dir/'grassroot.sqlite3'
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_migrations VALUES(1);
            CREATE TABLE IF NOT EXISTS puzzles(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS puzzle_versions(id TEXT, version INTEGER, body TEXT NOT NULL, PRIMARY KEY(id,version));
            CREATE TABLE IF NOT EXISTS attempts(id TEXT PRIMARY KEY, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS visit_events(attempt_id TEXT, idx INTEGER, body TEXT NOT NULL, PRIMARY KEY(attempt_id,idx));
            CREATE TABLE IF NOT EXISTS command_events(attempt_id TEXT, idx INTEGER, body TEXT NOT NULL, PRIMARY KEY(attempt_id,idx));
            CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, body TEXT NOT NULL, PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS imports(source TEXT PRIMARY KEY);
            ''')
        self.import_report = self.import_json()
        # Restart never resumes an interrupted run.
        for record in self.list_attempts():
            if not record.get('endedAt'):
                record.update(stopReason='INTERRUPTED', endedAt=int(time.time()*1000), summary=None)
                self.save_attempt(record['id'], record)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def import_json(self):
        report = {'imported': [], 'skipped': [], 'errors': []}
        candidates = [(f, 'puzzles') for f in sorted((self.dir/'puzzles').glob('*.json'))]
        candidates += [(f, 'attempts') for f in sorted((self.dir/'attempts').glob('*.json'))]
        cal = self.dir/'projector_calibration.json'
        if cal.exists(): candidates.append((cal, 'calibration'))
        with self.connect() as db:
            for path, kind in candidates:
                source = str(path.resolve())
                if db.execute('SELECT 1 FROM imports WHERE source=?', (source,)).fetchone():
                    report['skipped'].append(source)
                    continue
                try:
                    body = json.loads(path.read_text())
                    if kind == 'puzzles':
                        p = Puzzle.model_validate(body)
                        db.execute('INSERT OR IGNORE INTO puzzles VALUES(?,?)', (p.id, json.dumps(body)))
                        db.execute('INSERT OR IGNORE INTO puzzle_versions VALUES(?,?,?)', (p.id,p.version,json.dumps(body)))
                    elif kind == 'attempts':
                        if not isinstance(body.get('id'), str): raise ValueError('attempt has no id')
                        self._write_attempt(db, body['id'], body)
                    else:
                        ProjectorCalibration.model_validate(body)
                        db.execute('INSERT OR IGNORE INTO records VALUES(?,?,?)', ('calibrations','projector',json.dumps(body)))
                    db.execute('INSERT INTO imports VALUES(?)', (source,))
                    report['imported'].append(source)
                except (ValueError, TypeError, KeyError) as e:
                    report['errors'].append({'source':source,'error':str(e)})
        (self.dir/'sqlite_import_report.json').write_text(json.dumps(report, indent=2))
        return report

    def list_puzzles(self):
        out = {p.id:p for p in [Puzzle.model_validate_json(f.read_text()) for f in sorted((FIXTURES/'puzzles').glob('*.json'))]}
        with self.connect() as db:
            for body, in db.execute('SELECT body FROM puzzles ORDER BY id'):
                p = Puzzle.model_validate_json(body); out[p.id] = p
        return list(out.values())

    def list_library(self):
        with self.connect() as db:
            edited = {row[0] for row in db.execute('SELECT id FROM puzzles')}
        return [{**p.model_dump(mode='json'), 'builtin':self.is_builtin(p.id), 'edited':p.id in edited} for p in self.list_puzzles()]

    def save_puzzle(self, p):
        body = p.model_dump_json()
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO puzzles VALUES(?,?)', (p.id,body))
            # Preserve historical versions rather than overwriting their geometry.
            db.execute('INSERT OR IGNORE INTO puzzle_versions VALUES(?,?,?)', (p.id,p.version,body))

    def delete_puzzle(self, puzzle_id):
        with self.connect() as db:
            count = db.execute('DELETE FROM puzzles WHERE id=?', (puzzle_id,)).rowcount
        return ('reverted' if self.is_builtin(puzzle_id) else 'deleted') if count else 'missing'

    def load_calibration(self):
        body = self.get_record('calibrations','projector')
        return ProjectorCalibration.model_validate(body) if body else None

    def save_calibration(self, c):
        self.put_record('calibrations','projector',c.model_dump(mode='json'))

    def _write_attempt(self, db, attempt_id, record):
        db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?)',(attempt_id,json.dumps(record)))
        for table, key in [('visit_events','events'),('command_events','commands')]:
            db.execute(f'DELETE FROM {table} WHERE attempt_id=?',(attempt_id,))
            db.executemany(f'INSERT INTO {table} VALUES(?,?,?)', [(attempt_id,i,json.dumps(ev)) for i,ev in enumerate(record.get(key,[]))])

    def save_attempt(self, attempt_id, record):
        with self.connect() as db: self._write_attempt(db,attempt_id,record)

    def list_attempts(self):
        with self.connect() as db:
            return sorted([json.loads(r[0]) for r in db.execute('SELECT body FROM attempts')],key=lambda r:r.get('startedAt',0))

    def list_records(self, kind):
        self._kind(kind)
        with self.connect() as db:
            return [json.loads(r[0]) for r in db.execute('SELECT body FROM records WHERE kind=? ORDER BY id',(kind,))]

    def get_record(self, kind, id):
        self._kind(kind)
        with self.connect() as db:
            r = db.execute('SELECT body FROM records WHERE kind=? AND id=?',(kind,id)).fetchone()
        return json.loads(r[0]) if r else None

    def put_record(self, kind, id, body):
        self._kind(kind)
        with self.connect() as db: db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(kind,id,json.dumps(body)))

    def _kind(self, kind):
        if kind not in KINDS: raise ValueError('unsupported record kind')
