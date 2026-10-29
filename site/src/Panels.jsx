import { useMemo, useState } from "react";
import { fmtPct } from "./util.js";

const W = 720;

function LineChart({ series, label, height = 240, fmt, band }) {
  const H = height;
  const M = { l: 52, r: 12, t: 12, b: 26 };
  const xs = series.map((p) => new Date(p.date).getTime());
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const ys = series.flatMap((p) => (band ? [p.lo, p.hi] : [p.v]));
  const y1 = Math.max(...ys);
  const x = (t) => M.l + ((t - x0) / (x1 - x0)) * (W - M.l - M.r);
  const y = (v) => M.t + (1 - v / y1) * (H - M.t - M.b);
  const years = [...new Set(series.map((p) => p.date.slice(0, 4)))];
  const path = series.map((p, i) => `${i ? "L" : "M"}${x(new Date(p.date).getTime())},${y(p.v)}`).join("");
  const poly = band && [
    ...series.map((p) => `${x(new Date(p.date).getTime())},${y(p.hi)}`),
    ...[...series].reverse().map((p) => `${x(new Date(p.date).getTime())},${y(p.lo)}`),
  ].join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {[0, 0.25, 0.5, 0.75, 1].map((f) => (
        <g key={f}>
          <line className="axis" x1={M.l} x2={W - M.r} y1={y(f * y1)} y2={y(f * y1)} />
          <text x={M.l - 6} y={y(f * y1) + 4} textAnchor="end">{fmt(f * y1)}</text>
        </g>
      ))}
      {years.filter((_, i) => i % 2 === 0).map((yr) => (
        <text key={yr} x={x(new Date(`${yr}-01-01`).getTime())} y={H - 6} textAnchor="middle">{yr}</text>
      ))}
      {poly && <polygon points={poly} fill="var(--band80)" />}
      <path className="med" d={path} />
    </svg>
  );
}

export function Events({ events }) {
  const [who, setWho] = useState("all");
  const list = useMemo(
    () => events.filter((e) => who === "all" || (who === "other" ? !["LLY", "NVO"].includes(e.security) : e.security === who)),
    [events, who],
  );
  const big = [...list].sort((a, b) => Math.abs(b.car_m1p1) - Math.abs(a.car_m1p1)).slice(0, 8);
  const recent = [...list].slice(-6).reverse();
  const H = 260;
  const M = { l: 50, r: 12, t: 12, b: 26 };
  const t0 = new Date("2017-01-01").getTime();
  const t1 = new Date("2026-12-31").getTime();
  const cap = 0.3;
  const x = (d) => M.l + ((new Date(d).getTime() - t0) / (t1 - t0)) * (W - M.l - M.r);
  const y = (v) => M.t + (1 - (Math.max(-cap, Math.min(cap, v)) + cap) / (2 * cap)) * (H - M.t - M.b);
  const row = (e) => (
    <tr key={e.event_id + e.security}>
      <td className="num">{e.first_day0}</td>
      <td>{e.security}</td>
      <td>{e.title}</td>
      <td className={`r num ${e.car_m1p1 >= 0 ? "up" : "down"}`}>{fmtPct(e.car_m1p1)}</td>
    </tr>
  );
  return (
    <div className="card">
      <div className="seg" role="radiogroup" aria-label="Whose events">
        {[["all", "All"], ["LLY", "Lilly"], ["NVO", "Novo"], ["other", "Others"]].map(([k, l]) => (
          <label key={k}>
            <input type="radio" name="who" checked={who === k} onChange={() => setWho(k)} />
            {l}
          </label>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${list.length} news events, each a dot at its date and its abnormal three-day return`}>
        {[-0.3, -0.15, 0, 0.15, 0.3].map((v) => (
          <g key={v}>
            <line className="axis" x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} />
            <text x={M.l - 6} y={y(v) + 4} textAnchor="end">{v > 0 ? "+" : v < 0 ? "−" : ""}{Math.abs(v * 100)}%</text>
          </g>
        ))}
        {[2018, 2020, 2022, 2024, 2026].map((yr) => (
          <text key={yr} x={x(`${yr}-01-01`)} y={H - 6} textAnchor="middle">{yr}</text>
        ))}
        {list.map((e) => (
          <circle key={e.event_id + e.security} cx={x(e.first_day0)} cy={y(e.car_m1p1)} r="4.5"
            fill={e.car_m1p1 >= 0 ? "var(--up)" : "var(--down)"} opacity="0.65" stroke="var(--bg)">
            <title>{`${e.first_day0} ${e.security}: ${e.title} (${fmtPct(e.car_m1p1)})`}</title>
          </circle>
        ))}
      </svg>
      <p className="small">
        Each dot is a dated piece of news; height is how far the stock moved beyond what the market and common
        factors explain over the three days around it (capped at ±30% for the chart).
      </p>
      <div className="scroll">
        <table>
          <caption><b>Biggest reactions</b></caption>
          <thead><tr><th>Date</th><th>Stock</th><th>News</th><th className="r">Move</th></tr></thead>
          <tbody>{big.map(row)}</tbody>
        </table>
      </div>
      <div className="scroll" style={{ marginTop: 12 }}>
        <table>
          <caption><b>Most recent</b></caption>
          <thead><tr><th>Date</th><th>Stock</th><th>News</th><th className="r">Move</th></tr></thead>
          <tbody>{recent.map(row)}</tbody>
        </table>
      </div>
    </div>
  );
}

export function Valuation({ val }) {
  const l = val.latest;
  const series = val.weekly.map((w) => ({ date: w.date, v: w.peak.median, lo: w.peak.low, hi: w.peak.high }));
  return (
    <div className="grid2">
      <div className="card">
        <LineChart series={series} band fmt={(v) => `$${Math.round(v)}bn`}
          label="Peak yearly GLP-1 sales that Lilly's share price implies, weekly since 2019, with the range across assumptions" />
        <p className="small">Line: middle assumption. Band: the range across discount rates, margins and how long sales stay at peak.</p>
      </div>
      <div className="card">
        <h3>Today</h3>
        <p>
          Lilly is worth about <b className="num">${Math.round(l.ev_bn).toLocaleString("en-US")}bn</b>. After valuing its
          ordinary business at what peers are worth, the rest only adds up if tirzepatide (Mounjaro, Zepbound)
          eventually sells about <b className="num">${Math.round(l.peak_c.median)}bn</b> a year at its peak (range{" "}
          <span className="num">${Math.round(l.peak_c.low)}–{Math.round(l.peak_c.high)}bn</span>), against{" "}
          <span className="num">${l.glp1_ttm_bn.toFixed(1)}bn</span> over the last twelve months.
        </p>
        <p className="small">
          It is an upper bound: all of Lilly's premium over peers is credited to tirzepatide. News days (
          {val.news.news_days} of {val.news.all_days}) account for {Math.round(val.news.share_of_total * 100)}% of the stock's
          log return since {val.news.from}.
        </p>
      </div>
    </div>
  );
}

export function Scorecard({ back, card }) {
  const test = back.filter((c) => c.period === "test" && c.h <= 126);
  const get = (tk, h, m) => test.find((c) => c.ticker === tk && c.h === h && c.model === m);
  const models = ["B0", "B1", "M2"];
  const names = { B0: "Random walk", B1: "GARCH", M2: "This model" };
  return (
    <div className="grid2">
      <div className="card">
        <h3>How often the 80% range held (backtest, Nov 2025 to now)</h3>
        <p className="small">A well-calibrated 80% range holds 80% of the time. Few independent periods, so treat gaps as rough.</p>
        <div className="scroll">
          <table>
            <thead>
              <tr><th>Stock</th><th>Days ahead</th>{models.map((m) => <th key={m} className="r">{names[m]}</th>)}</tr>
            </thead>
            <tbody>
              {["LLY", "NVO"].flatMap((tk) => [21, 63, 126].map((h) => (
                <tr key={tk + h}>
                  <td>{tk}</td><td>{h}</td>
                  {models.map((m) => <td key={m} className="r num">{Math.round(get(tk, h, m).c80 * 100)}%</td>)}
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <h3>Live record</h3>
        {card.summary.length ? (
          <table>
            <thead><tr><th>Stock</th><th>Days</th><th className="r">Scored</th><th className="r">In 80% range</th></tr></thead>
            <tbody>
              {card.summary.map((s) => (
                <tr key={s.ticker + s.h}><td>{s.ticker}</td><td>{s.h}</td><td className="r num">{s.n}</td><td className="r num">{Math.round(s.coverage80 * 100)}%</td></tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>
            Nothing scored yet. Every weekday evening a new forecast is added to a public, hash-chained ledger in the
            repository and scored when its horizon passes; the first one-day forecasts resolve after the next
            trading day.
          </p>
        )}
      </div>
    </div>
  );
}
