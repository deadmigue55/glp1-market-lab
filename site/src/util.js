export const fmtPct = (x, d = 1) => {
  const t = Math.abs(x * 100).toFixed(d);
  return +t === 0 ? `${t}%` : `${x >= 0 ? "+" : "−"}${t}%`;
};
export const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
export const fmtMoney = (x) =>
  x >= 1000 ? `$${Math.round(x).toLocaleString("en-US")}` : `$${x.toFixed(x >= 100 ? 0 : 2)}`;

// Weekdays after a date (US holidays are not skipped, so dates are approximate).
export function addWeekdays(iso, n) {
  const d = new Date(`${iso}T12:00:00Z`);
  let left = n;
  while (left > 0) {
    d.setUTCDate(d.getUTCDate() + 1);
    const w = d.getUTCDay();
    if (w !== 0 && w !== 6) left--;
  }
  return d;
}
export const fmtDate = (d) =>
  d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });

// "Nice" price ticks inside [lo, hi].
export function niceTicks(lo, hi, count = 5) {
  const span = hi - lo;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) out.push(v);
  return out;
}
