// Checks the browser simulator against the Python forecast: with no catalysts and no width
// factor it must reproduce M1's quantiles up to the Monte Carlo noise of both sides.
import { readFileSync } from "node:fs";
import { simulate } from "../src/sim.js";

const data = JSON.parse(readFileSync(new URL("../public/data/forecast.json", import.meta.url)));
// Of the half-width of the 80% interval. Python's own 2000-path noise reaches 0.09 at the worst
// level, and it changes every night, so a tight bound would fail the deploy at random.
const TOL = 0.25;
let worst = 0;
let bad = 0;
for (const stock of data.stocks) {
  const { q } = simulate(stock, null, { n: 60000, seed: 7, k: false });
  for (const h of Object.keys(stock.m1)) {
    const py = stock.m1[h];
    const js = q[h];
    const half = (py[89] - py[9]) / 2;
    for (const i of [4, 9, 24, 49, 74, 89, 94]) {
      const d = Math.abs(js[i] - py[i]) / half;
      worst = Math.max(worst, d);
      if (d > TOL) {
        bad++;
        console.log(`${stock.ticker} h=${h} level=${i + 1}%: js ${js[i].toFixed(4)} py ${py[i].toFixed(4)} (${d.toFixed(3)})`);
      }
    }
  }
}
console.log(`worst difference ${worst.toFixed(3)} of the 80% half-width (tolerance ${TOL})`);
process.exit(bad ? 1 : 0);
