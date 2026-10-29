import { addWeekdays, fmtDate, fmtMoney, niceTicks } from "./util.js";

const W = 720;
const H = 340;
const M = { l: 58, r: 14, t: 14, b: 30 };

export default function FanChart({ stock, result, base, view, sel, catalysts }) {
  const grid = result.grid.filter((h) => h <= view);
  const hist = stock.history.slice(-Math.min(90, Math.max(30, Math.round(view * 0.6))));
  const nh = hist.length - 1;
  const price = (lr) => stock.spot * Math.exp(lr);
  const at = (h, i) => price(result.q[h][i]);
  const days = [...Array(nh + 1).keys()].map((i) => i - nh);
  const lo = Math.min(...hist.map((p) => p.close), ...grid.map((h) => at(h, 4)));
  const hi = Math.max(...hist.map((p) => p.close), ...grid.map((h) => at(h, 94)));
  const x = (d) => M.l + ((d + nh) / (nh + view)) * (W - M.l - M.r);
  const y = (p) => M.t + (1 - (Math.log(p) - Math.log(lo)) / (Math.log(hi) - Math.log(lo))) * (H - M.t - M.b);
  const poly = (a, b) =>
    [...grid.map((h) => `${x(h)},${y(at(h, b))}`), ...[...grid].reverse().map((h) => `${x(h)},${y(at(h, a))}`)].join(" ");
  const line = (i) => grid.map((h, j) => `${j ? "L" : "M"}${x(h)},${y(at(h, i))}`).join("");
  const histPath = hist.map((p, i) => `${i ? "L" : "M"}${x(days[i])},${y(p.close)}`).join("");
  const ticks = niceTicks(lo, hi, 5);
  const xt = [0, Math.round(view / 3), Math.round((2 * view) / 3), view];
  const label = `${stock.ticker} price: last ${hist.length} days and a forecast to ${view} trading days. In ${sel} days the 80% range is ${fmtMoney(at(sel, 9))} to ${fmtMoney(at(sel, 89))}.`;
  const selGrid = result.q[sel] ? sel : grid[grid.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      {ticks.map((t) => (
        <g key={t}>
          <line className="axis" x1={M.l} x2={W - M.r} y1={y(t)} y2={y(t)} />
          <text x={M.l - 6} y={y(t) + 4} textAnchor="end">{fmtMoney(t)}</text>
        </g>
      ))}
      {xt.map((d) => (
        <text key={d} x={x(d)} y={H - 8} textAnchor={d === view ? "end" : "middle"}>
          {d === 0 ? "today" : `+${d}d`}
        </text>
      ))}
      <polygon points={poly(4, 94)} fill="var(--band80)" opacity="0.55" />
      <polygon points={poly(9, 89)} fill="var(--band80)" />
      <polygon points={poly(24, 74)} fill="var(--band50)" />
      {base && <path d={base.grid.filter((h) => h <= view).map((h, j) => `${j ? "L" : "M"}${x(h)},${y(price(base.q[h][49]))}`).join("")} fill="none" stroke="var(--muted)" strokeDasharray="4 4" />}
      <path className="hist" d={histPath} />
      <path className="med" d={line(49)} />
      {catalysts.filter((c) => c.offset <= view).map((c) => (
        <g className="cat" key={c.id}>
          <line x1={x(c.offset)} x2={x(c.offset)} y1={M.t} y2={H - M.b} />
          <text x={x(c.offset) + 4} y={M.t + 10 + 12 * (c.row ?? 0)}>{c.short}</text>
        </g>
      ))}
      <line x1={x(selGrid)} x2={x(selGrid)} y1={M.t} y2={H - M.b} stroke="var(--fg)" strokeWidth="1" opacity="0.5" />
      {[9, 49, 89].map((i) => (
        <circle key={i} cx={x(selGrid)} cy={y(at(selGrid, i))} r="4" fill={i === 49 ? "var(--accent)" : "var(--bg)"} stroke="var(--accent)" strokeWidth="2" />
      ))}
      <title>{`${label} ${fmtDate(addWeekdays(stock.origin, sel))}`}</title>
    </svg>
  );
}
