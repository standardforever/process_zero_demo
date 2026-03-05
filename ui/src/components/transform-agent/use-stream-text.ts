/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useState } from "react";

export function useStreamText(text: string, active = true, startDelay = 120): { shown: string; done: boolean } {
  const [shown, setShown] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!active) return;

    setShown("");
    setDone(false);

    let index = 0;
    let stepTimer: ReturnType<typeof setTimeout> | undefined;

    const startTimer = setTimeout(() => {
      const tick = () => {
        index += 1;
        setShown(text.slice(0, index));

        if (index >= text.length) {
          setDone(true);
          return;
        }

        const char = text[index - 1] ?? "";
        const delay = char === "\n" ? 55 : char === "." || char === "!" || char === "?" ? 45 : 14;
        stepTimer = setTimeout(tick, delay);
      };

      tick();
    }, startDelay);

    return () => {
      clearTimeout(startTimer);
      if (stepTimer) clearTimeout(stepTimer);
    };
  }, [active, startDelay, text]);

  if (!active) return { shown: text, done: true };
  return { shown, done };
}
