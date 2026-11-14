import { useEffect, useRef, useState } from 'react';

export type Act = 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT';
const DEAD_ZONE = 0.5;

/** Browser Gamepad adapter: button 0 toggles recording (rising edge, server also debounces),
 * d-pad / left stick give discrete one-cell moves and 90° turns. */
export function useGamepad(onToggle: () => void, onAct: (a: Act) => void) {
  const [name, setName] = useState<string | null>(null);
  const prev = useRef<Record<string, boolean>>({});
  useEffect(() => {
    let raf = 0;
    const loop = () => {
      const gp = navigator.getGamepads?.().find((g) => g);
      setName(gp?.id ?? null);
      if (gp) {
        const ax = gp.axes[0] ?? 0, ay = gp.axes[1] ?? 0;
        const now: Record<string, boolean> = {
          toggle: !!gp.buttons[0]?.pressed,
          FORWARD: !!gp.buttons[12]?.pressed || ay < -DEAD_ZONE,
          BACKWARD: !!gp.buttons[13]?.pressed || ay > DEAD_ZONE,
          LEFT: !!gp.buttons[14]?.pressed || ax < -DEAD_ZONE,
          RIGHT: !!gp.buttons[15]?.pressed || ax > DEAD_ZONE,
        };
        for (const k of Object.keys(now)) {
          if (now[k] && !prev.current[k]) (k === 'toggle' ? onToggle() : onAct(k as Act));
        }
        prev.current = now;
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [onToggle, onAct]);
  return name;
}
