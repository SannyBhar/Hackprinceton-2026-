import { afterEach, expect, it, vi } from 'vitest';
import { api } from './client';

afterEach(() => vi.unstubAllGlobals());

it('keeps validation endpoint, request and authoritative planned entries intact', async () => {
  const result = { ok: true, errors: [], plannedEntries: [{ row: 1, col: 0 }] };
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => result });
  vi.stubGlobal('fetch', fetch);
  const program = [{ op: 'START' as const }, { op: 'FORWARD' as const, steps: 1 }, { op: 'STOP' as const }];
  expect(await api.validate(program)).toEqual(result);
  expect(fetch).toHaveBeenCalledWith('/api/program/validate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instructions: program }),
  });
});

it('propagates validation HTTP errors through the shared client', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'invalid program' }) }));
  await expect(api.validate([])).rejects.toThrow('invalid program');
});
