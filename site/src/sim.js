// Monte Carlo behind the fan chart. Pure functions: the page runs them in a Web Worker and
// scripts/verify-sim.mjs runs the same code under Node and compares it with the Python forecast.
// Inputs come from forecast.json, written nightly by `glp1 nightly`.

export const HORIZONS = [1, 5, 21, 63, 126, 252]; // horizons the conformal factor is kept for

export function rng(seed) {
  let a = seed >>> 0; // mulberry32
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function normal(r) {
  let u = 0;
  while (u === 0) u = r();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r());
}

// Draw from a distribution known by its 99 quantiles (levels 0.01..0.99): linear between them,
// exponential tails beyond.
export function fromQuantiles(q, u) {
  const p = u * 100 - 1;
  if (p < 0) return q[0] + (q[1] - q[0]) * Math.log(Math.max(u, 1e-12) / 0.01);
  if (p >= 98) return q[98] - (q[98] - q[97]) * Math.log(Math.max(1 - u, 1e-12) / 0.01);
  const i = Math.floor(p);
  const f = p - i;
  return q[i] * (1 - f) + q[i + 1] * f;
}

// Conformal width factor at any horizon: linear in log(h) between the stored horizons.
export function kAt(k, h) {
  if (h <= HORIZONS[0]) return k[HORIZONS[0]];
  for (let i = 1; i < HORIZONS.length; i++) {
    if (h <= HORIZONS[i]) {
      const a = HORIZONS[i - 1];
      const b = HORIZONS[i];
      const f = (Math.log(h) - Math.log(a)) / (Math.log(b) - Math.log(a));
      return k[a] * (1 - f) + k[b] * f;
    }
  }
  return k[HORIZONS[HORIZONS.length - 1]];
}

function quantilesOf(sorted, levels) {
  const n = sorted.length;
  return levels.map((l) => {
    const p = l * (n - 1);
    const i = Math.floor(p);
    return i + 1 < n ? sorted[i] + (sorted[i + 1] - sorted[i]) * (p - i) : sorted[i];
  });
}

export const LEVELS = Array.from({ length: 99 }, (_, i) => (i + 1) / 100);

/**
 * stock    one entry of forecast.json `stocks`
 * scenario null = the model as the nightly run publishes it (before the width factor), or
 *          { earnings: {offset, outcomes:[{probability,mean,sd}], pick: null|index} | null,
 *            approval: {offset, pMarket, pUser, size, pick: null|"approved"|"rejected"} | null }
 * k        use the conformal width factor (false only for the check against Python)
 * Returns { grid, q: {h: 99 log-return quantiles}, pUp: {h} }.
 */
export function simulate(stock, scenario, { n = 6000, seed = 1, k = true } = {}) {
  const grid = Object.keys(stock.diffusion_q).map(Number).sort((a, b) => a - b);
  const jp = stock.jumps;
  const earn = scenario?.earnings ?? null;
  const appr = scenario?.approval ?? null;
  const sched = scenario ? stock.sched_offsets.slice(earn ? 1 : 0) : stock.sched_offsets;
  const rDiff = rng(seed * 11 + 1);
  const rUns = rng(seed * 11 + 2);
  const rSch = rng(seed * 11 + 3);
  const rEar = rng(seed * 11 + 4);
  const rApp = rng(seed * 11 + 5);
  const x = new Map(grid.map((h) => [h, new Float64Array(n)]));
  const lam = jp.unscheduled_per_year / 252;
  const mixMean = earn ? earn.outcomes.reduce((s, o) => s + o.probability * o.mean, 0) : 0;
  const maxH = grid[grid.length - 1];
  for (let i = 0; i < n; i++) {
    const u = rDiff();
    const jumps = []; // [time, size]
    for (let t = -Math.log(1 - rUns()) / lam; t <= maxH; t += -Math.log(1 - rUns()) / lam) {
      jumps.push([Math.ceil(t), normal(rUns) * jp.unscheduled_sd]);
    }
    for (const off of sched) jumps.push([off, normal(rSch) * jp.scheduled_sd]);
    if (earn) {
      const ue = rEar();
      const z = normal(rEar);
      let o = earn.pick;
      if (o === null || o === undefined) {
        let c = 0;
        o = earn.outcomes.length - 1;
        for (let j = 0; j < earn.outcomes.length; j++) {
          c += earn.outcomes[j].probability;
          if (ue < c) { o = j; break; }
        }
      }
      // the model's own mix is centred: the event study found no average earnings-day move
      const shift = earn.pick === null || earn.pick === undefined ? -mixMean : 0;
      jumps.push([earn.offset, earn.outcomes[o].mean + shift + earn.outcomes[o].sd * z]);
    }
    if (appr) {
      const ua = rApp();
      normal(rApp); // keeps the stream the same whatever the setting
      const approved = appr.pick === "approved" ? true : appr.pick === "rejected" ? false : ua < appr.pUser;
      jumps.push([appr.offset, approved ? (1 - appr.pMarket) * appr.size : -appr.pMarket * appr.size]);
    }
    for (const h of grid) {
      let v = fromQuantiles(stock.diffusion_q[h], u);
      for (const [t, s] of jumps) if (t <= h) v += s;
      x.get(h)[i] = v;
    }
  }
  const q = {};
  const pUp = {};
  for (const h of grid) {
    const a = x.get(h).sort();
    let qs = quantilesOf(a, LEVELS);
    if (k) {
      const f = kAt(stock.k, h);
      qs = qs.map((v) => qs[49] + (v - qs[49]) * f);
    }
    q[h] = qs;
    const j = qs.findIndex((v) => v > 0);
    pUp[h] = j === -1 ? 0 : j === 0 ? 1 : 1 - (j - 1 + (0 - qs[j - 1]) / (qs[j] - qs[j - 1]) + 1) / 100;
  }
  return { grid, q, pUp };
}
