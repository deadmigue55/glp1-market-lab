import { simulate } from "./sim.js";

// One message in, one result out: { id, stock, scenario, opts } -> { id, result }
self.onmessage = (e) => {
  const { id, jobs } = e.data;
  self.postMessage({ id, results: jobs.map((j) => simulate(j.stock, j.scenario, j.opts)) });
};
