import { useEffect, useState } from "react";
import Forecast from "./Forecast.jsx";
import { Events, Scorecard, Valuation } from "./Panels.jsx";

const REPO = "https://github.com/deadmigue55/glp1-market-lab";
const FILES = ["forecast", "events", "valuation", "backtest", "scorecard"];

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme ?? "");
  const dark = theme ? theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  const toggle = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch { /* private mode */ }
    setTheme(next);
  };
  return [dark, toggle];
}

export default function App() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [ticker, setTicker] = useState("LLY");
  const [dark, toggle] = useTheme();

  useEffect(() => {
    Promise.all(FILES.map((f) => fetch(`./data/${f}.json`).then((r) => { if (!r.ok) throw new Error(f); return r.json(); })))
      .then((v) => setData(Object.fromEntries(FILES.map((f, i) => [f, v[i]]))))
      .catch((e) => setErr(e.message));
  }, []);

  const stock = data?.forecast.stocks.find((s) => s.ticker === ticker);
  return (
    <>
      <div className="wrap">
        <header className="top">
          <strong>Weight of News</strong>
          <nav aria-label="Sections">
            <a href="#forecast">Forecast</a><a href="#news">News</a><a href="#value">Valuation</a><a href="#record">Record</a><a href={REPO}>Code</a>
            <button className="theme" onClick={toggle}>{dark ? "Light theme" : "Dark theme"}</button>
          </nav>
        </header>
        <main>
          <div className="hero">
            <h1>How GLP-1 news moves Lilly and Novo</h1>
            <p>
              Weight-loss drugs like Ozempic and Zepbound have reshaped two of the world's biggest drug makers. Pick how the
              next big announcements turn out and see how the range of likely share prices changes.
            </p>
            <div className="chips">
              <span className="chip warn">Not investment advice</span>
              <span className="chip">Shows the spread of outcomes, not a direction</span>
              {data && <span className="chip">Updated {data.forecast.generated.slice(0, 10)}, prices to {stock?.origin}</span>}
            </div>
          </div>

          {err && <p role="alert">The data failed to load ({err}). Try again later.</p>}
          {!data && !err && <p role="status">Loading…</p>}
          {data && (
            <>
              <section id="forecast" aria-labelledby="h-forecast">
                <h2 id="h-forecast">Forecast: change the news, see the range move</h2>
                <p className="lead">
                  The shaded fan is where the share price is likely to be: the darkest band holds half of simulated outcomes,
                  the next four in five and the lightest nine in ten. It comes from a volatility model plus jumps for dated
                  events, widened where past forecasts of this kind were too confident.
                </p>
                <div className="tabs" role="group" aria-label="Company">
                  {data.forecast.stocks.map((s) => (
                    <button key={s.ticker} aria-pressed={ticker === s.ticker} onClick={() => setTicker(s.ticker)}>
                      {s.ticker === "LLY" ? "Eli Lilly" : "Novo Nordisk"}
                    </button>
                  ))}
                </div>
                <Forecast key={ticker} stock={stock} />
              </section>

              <section id="news" aria-labelledby="h-news">
                <h2 id="h-news">What past news did</h2>
                <p className="lead">
                  {data.events.length} dated announcements since 2018: trial results, regulatory decisions, earnings and
                  policy. On average the moves cancel out; guidance changes seem to matter more than headline weight loss,
                  and a few days move a stock a lot.
                </p>
                <Events events={data.events} />
              </section>

              <section id="value" aria-labelledby="h-value">
                <h2 id="h-value">What the share price already assumes</h2>
                <p className="lead">
                  Working backwards from Lilly's market value: how big would its weight-loss business have to become for
                  today's price to be fair?
                </p>
                <Valuation val={data.valuation} />
              </section>

              <section id="record" aria-labelledby="h-record">
                <h2 id="h-record">Track record</h2>
                <p className="lead">
                  Forecasts are only worth something if they are checked. Past ranges are tested against what happened, and
                  every new forecast is locked into a public ledger and scored once its outcome is known.
                </p>
                <Scorecard back={data.backtest} card={data.scorecard} />
              </section>
            </>
          )}
        </main>
        <footer>
          <p>
            Not investment advice. Statistics about the past and model output; nothing here is a recommendation to buy or
            sell. Free public data only (Yahoo Finance prices, SEC filings, Kalshi, Wikipedia). Methods, limits and the
            full study are in the <a href={REPO}>repository</a>.
          </p>
        </footer>
      </div>
    </>
  );
}
