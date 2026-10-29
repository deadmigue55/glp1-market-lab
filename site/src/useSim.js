import { useEffect, useRef, useState } from "react";
import { simulate } from "./sim.js";

// Runs the simulations in a Web Worker; falls back to the main thread if workers are unavailable.
export function useSim(jobs, key) {
  const [results, setResults] = useState(null);
  const worker = useRef(null);
  const seq = useRef(0);
  useEffect(() => {
    if (!jobs) return undefined;
    const id = ++seq.current;
    try {
      if (!worker.current) {
        worker.current = new Worker(new URL("./sim.worker.js", import.meta.url), { type: "module" });
      }
      worker.current.onmessage = (e) => {
        if (e.data.id === seq.current) setResults(e.data.results);
      };
      worker.current.postMessage({ id, jobs });
    } catch {
      setResults(jobs.map((j) => simulate(j.stock, j.scenario, j.opts)));
    }
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => () => worker.current?.terminate(), []);
  return results;
}
