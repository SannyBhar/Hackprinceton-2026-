import { useEffect, useRef, useState } from 'react';
import type { Snapshot, WsMessage } from './types';

/** Subscribes to authoritative backend state. Reconnects with backoff; ignores
 * any message whose seq is not newer than what we already applied, so a
 * reconnect never replays/duplicates visits. */
export function useSession() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const lastSeq = useRef(-1);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    let retry = 300;
    let timer: number | undefined;

    const open = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      let first = true;
      ws.onopen = () => { setConnected(true); retry = 300; };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data) as WsMessage;
        // The first message on every (re)connection is a full snapshot: accept it
        // unconditionally (handles backend restarts that reset seq). After that,
        // only strictly newer events apply.
        if (!first && msg.seq <= lastSeq.current) return;
        first = false;
        if (msg.type === 'snapshot') {
          lastSeq.current = msg.seq;
          setSnap(msg.payload);
        } else if (msg.type === 'pose') {
          lastSeq.current = msg.seq;
          setSnap((s) => (s ? { ...s, pose: msg.payload } : s));
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) timer = window.setTimeout(open, (retry = Math.min(retry * 2, 4000)));
      };
    };
    open();
    return () => { closed = true; window.clearTimeout(timer); ws?.close(); };
  }, []);

  return { snap, connected };
}
