import { useMemo, useState } from "react";
import FanChart from "./FanChart.jsx";
import { useSim } from "./useSim.js";
import { addWeekdays, fmtDate, fmtMoney, fmtPct } from "./util.js";

const VIEWS = [21, 63, 126, 252];
const N = 6000;
const NONE = { earn: null, p: null, pick: null };

// Scenario for the simulator: `choice` holds what the visitor picked; null means the model's own mix.
function scenario(stock, choice) {
  const earn = stock.catalysts.find((c) => c.model === "earnings" && c.outcomes?.length);
  const appr = stock.catalysts.find((c) => c.model === "approval" && c.market);
  return {
    earnings: earn && { offset: earn.offset, outcomes: earn.outcomes, pick: choice.earn },
    approval: appr && {
      offset: appr.offset,
      pMarket: appr.market.probability,
      pUser: choice.p ?? appr.market.probability,
      size: stock.jumps.unscheduled_sd,
      pick: choice.pick,
    },
  };
}

export default function Forecast({ stock }) {
  const [view, setView] = useState(126);
  const [sel, setSel] = useState(21);
  const [choice, setChoice] = useState(NONE);
  const earn = stock.catalysts.find((c) => c.model === "earnings" && c.outcomes?.length);
  const appr = stock.catalysts.find((c) => c.model === "approval" && c.market);
  const changed = choice.earn !== null || choice.p !== null || choice.pick !== null;

  const jobs = useMemo(() => {
    const o = { n: N, seed: 3 };
    return [
      { stock, scenario: scenario(stock, choice), opts: o },
      { stock, scenario: scenario(stock, NONE), opts: o },
      { stock, scenario: scenario(stock, { ...NONE, earn: choice.earn }), opts: o },
      { stock, scenario: scenario(stock, { ...NONE, p: choice.p, pick: choice.pick }), opts: o },
    ];
  }, [stock, choice]);
  const res = useSim(jobs, `${stock.ticker}|${choice.earn}|${choice.p}|${choice.pick}`);
  if (!res) return <div className="card" role="status">Running the simulation…</div>;
  const [full, baseRun, eOnly, aOnly] = res;

  const shown = full.grid.filter((h) => h <= view);
  const at = Math.min(sel, view);
  const med = (r, h) => stock.spot * Math.exp(r.q[h][49]);
  const lowHigh = (h) => [stock.spot * Math.exp(full.q[h][9]), stock.spot * Math.exp(full.q[h][89])];
  const [a, b] = lowHigh(at);
  const steps = [
    ["Model's own forecast", med(baseRun, at), false],
    ...(earn
      ? [[`Earnings: ${choice.earn === null ? "model mix" : earn.outcomes[choice.earn].label}`, med(eOnly, at) - med(baseRun, at), true]]
      : []),
    ...(appr ? [["FDA decision", med(aOnly, at) - med(baseRun, at), true]] : []),
  ];
  const inter = med(full, at) - med(baseRun, at) - steps.slice(1).reduce((s, r) => s + r[1], 0);
  const rows = [...steps, ...(Math.abs(inter) > 0.005 * stock.spot ? [["Both together", inter, true]] : [])];

  const cats = stock.catalysts
    .map((c, i) => ({
      ...c,
      short: c.model === "earnings" ? "earnings" : c.model === "approval" ? "FDA" : "",
      row: i,
    }))
    .filter((c) => c.model !== "info");

  return (
    <div className="grid2">
      <div className="card">
        <div className="seg" role="radiogroup" aria-label="Chart length">
          {VIEWS.map((v) => (
            <label key={v}>
              <input type="radio" name="view" checked={view === v} onChange={() => { setView(v); if (sel > v) setSel(v); }} />
              {v === 252 ? "1 year" : `${v} days`}
            </label>
          ))}
        </div>
        <FanChart stock={stock} result={full} base={changed ? baseRun : null} view={view} sel={at} catalysts={cats} />
        <label className="small" htmlFor="hz">
          Look at a point in time: {at} trading days ahead (about {fmtDate(addWeekdays(stock.origin, at))})
        </label>
        <input
          id="hz"
          className="range"
          type="range"
          min="0"
          max={shown.length - 1}
          value={Math.max(0, shown.indexOf(at))}
          onChange={(e) => setSel(shown[+e.target.value])}
        />
        <div className="readout" aria-live="polite">
          <div><b>{fmtMoney(a)}</b><span>10% chance below</span></div>
          <div><b>{fmtMoney(med(full, at))}</b><span>middle outcome</span></div>
          <div><b>{fmtMoney(b)}</b><span>10% chance above</span></div>
          <div><b>{Math.round(full.pUp[at] * 100)}%</b><span>chance above today's {fmtMoney(stock.spot)}</span></div>
        </div>
        {view === 252 && (
          <p className="small">
            One year out the band is very wide: the width factor learned from past misses is above 2 there, and the
            backtest has no out-of-sample year to confirm it.
          </p>
        )}
        <details>
          <summary>Show the numbers</summary>
          <div className="scroll">
            <table>
              <caption className="sr">Forecast by horizon</caption>
              <thead>
                <tr><th>Trading days</th><th className="r">10%</th><th className="r">25%</th><th className="r">Middle</th><th className="r">75%</th><th className="r">90%</th></tr>
              </thead>
              <tbody>
                {full.grid.map((h) => (
                  <tr key={h}>
                    <td>{h}</td>
                    {[9, 24, 49, 74, 89].map((i) => (
                      <td key={i} className="r num">{fmtMoney(stock.spot * Math.exp(full.q[h][i]))}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div className="stack">
        <div className="card">
          <h3>Choose how the news lands</h3>
          <p className="small">
            Defaults are the model's own odds and the prediction market's price. Change them and the fan redraws.
          </p>
          {earn && (
            <fieldset style={{ border: 0, padding: 0, margin: "10px 0" }}>
              <legend>
                <b>{earn.title}</b> <span className="small">(in {earn.offset} trading days)</span>
              </legend>
              <div className="seg">
                <label>
                  <input type="radio" name="earn" checked={choice.earn === null} onChange={() => setChoice({ ...choice, earn: null })} />
                  Model mix
                </label>
                {earn.outcomes.map((o, i) => (
                  <label key={o.label}>
                    <input type="radio" name="earn" checked={choice.earn === i} onChange={() => setChoice({ ...choice, earn: i })} />
                    {o.label.replace("guidance ", "")}
                  </label>
                ))}
              </div>
              <p className="small">
                {earn.outcomes
                  .map((o) => `${o.label.replace("guidance ", "")}: ${Math.round(o.probability * 100)}% of past reports (${o.n}), typical 3-day move ${fmtPct(o.mean)}`)
                  .join(" · ")}
              </p>
            </fieldset>
          )}
          {appr && (
            <fieldset style={{ border: 0, padding: 0, margin: "10px 0" }}>
              <legend>
                <b>FDA decision on CagriSema</b> <span className="small">(about {appr.offset} trading days)</span>
              </legend>
              <label className="small" htmlFor="pa">
                My chance of approval: {Math.round((choice.p ?? appr.market.probability) * 100)}% (the market says {Math.round(appr.market.probability * 100)}%)
              </label>
              <input
                id="pa"
                className="range"
                type="range"
                min="0"
                max="100"
                value={Math.round((choice.p ?? appr.market.probability) * 100)}
                onChange={(e) => setChoice({ ...choice, p: +e.target.value / 100, pick: null })}
              />
              <div className="seg">
                <label><input type="radio" name="pick" checked={choice.pick === null} onChange={() => setChoice({ ...choice, pick: null })} />Use my chance</label>
                <label><input type="radio" name="pick" checked={choice.pick === "approved"} onChange={() => setChoice({ ...choice, pick: "approved" })} />Approved</label>
                <label><input type="radio" name="pick" checked={choice.pick === "rejected"} onChange={() => setChoice({ ...choice, pick: "rejected" })} />Rejected</label>
              </div>
              <p className="small">
                Market price: {appr.market.title} Moves are sized from Novo's past unscheduled news days (±
                {(stock.jumps.unscheduled_sd * 100).toFixed(1)}%), split so that the market's own odds give zero average move.
              </p>
            </fieldset>
          )}
          {stock.catalysts.some((c) => c.model === "info") && (
            <p className="small">
              <b>Also on the calendar, not modelled:</b>{" "}
              {stock.catalysts.filter((c) => c.model === "info").map((c) => c.title).join("; ")}.
            </p>
          )}
          <button className="btn" onClick={() => setChoice(NONE)} disabled={!changed}>Reset to the model</button>
        </div>

        <div className="card">
          <h3>What moved the middle outcome</h3>
          <p className="small">At {at} trading days. Each bar is one choice, changed alone from the model's own forecast.</p>
          <Waterfall rows={rows} total={med(full, at)} />
        </div>
      </div>
    </div>
  );
}

function Waterfall({ rows, total }) {
  const max = Math.max(...rows.filter((r) => r[2]).map((r) => Math.abs(r[1])), 1e-9);
  return (
    <table>
      <caption className="sr">Change in the middle outcome by choice</caption>
      <tbody>
        {rows.map(([name, v, delta]) => (
          <tr key={name}>
            <td>{name}</td>
            <td className="r num">
              {delta ? (
                <>
                  <span className={v >= 0 ? "up" : "down"}>
                    {v >= 0 ? "+" : "−"}
                    {fmtMoney(Math.abs(v))}
                  </span>{" "}
                  <span className="bar" style={{ width: `${(Math.abs(v) / max) * 60}px`, background: v >= 0 ? "var(--up)" : "var(--down)" }} aria-hidden="true" />
                </>
              ) : (
                fmtMoney(v)
              )}
            </td>
          </tr>
        ))}
        <tr>
          <td><b>Your scenario</b></td>
          <td className="r num"><b>{fmtMoney(total)}</b></td>
        </tr>
      </tbody>
    </table>
  );
}
