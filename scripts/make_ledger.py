"""Assemble data/ledger/catalysts.csv: EDGAR-derived rows, then overrides and hand-sourced rows.

Run from the repo root: ``.venv/Scripts/python.exe -X utf8 scripts/make_ledger.py``.
Every hand-sourced row names the page its time came from; times printed in Eastern or
Central European time are converted to UTC here, never typed in UTC by hand.
"""

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import make_edgar_rows

from glp1 import ledger

TODAY = date(2026, 10, 28)
ET, CET = ZoneInfo("America/New_York"), ZoneInfo("Europe/Copenhagen")
W = make_edgar_rows.W
H2H = "pp weight loss, tirzepatide minus the active comparator in the same head-to-head trial"
PRN = "https://www.prnewswire.com/news-releases/"


def local(y, m, d, hh, mm, zone):
    return datetime(y, m, d, hh, mm, tzinfo=zone).astimezone(UTC)


def day_end(y, m, d, zone):
    """Time of day unknown: the last minute of the stated day, so the study uses a [0, +1] window."""
    return datetime(y, m, d, 23, 59, tzinfo=zone).astimezone(UTC)


# Overrides: edgar row id -> fields (an exact time from the company's own page beats the filing time)
OVERRIDES = {
    "NVO-20230808-select": {
        "occurred_at": datetime(2023, 8, 8, 9, 56, 6, tzinfo=UTC),
        "timing": "exact",
        "timestamp_source": "press_release",
        "source_url": "https://www.novonordisk.com/news-and-media/news-and-ir-materials/news-details.html?id=166301",
        "notes": "Lilly reported earnings the same day. Time from novonordisk.com (09:56:06 UTC); the 6-K was filed 12:09 UTC.",
    },
}

# (event_id, ticker, also, type, title, occurred_at, timing, source, url, surprise, basis, conf, notes)
# timing "exact" rows carry the time printed on the release page.
MANUAL = [
    (
        "LLY-20220428-surmount1",
        "LLY",
        "NVO",
        "trial_readout",
        "SURMOUNT-1: tirzepatide up to 22.5% weight loss",
        local(2022, 4, 28, 6, 15, ET),
        "exact",
        "press_release",
        PRN
        + "lillys-tirzepatide-delivered-up-to-22-5-weight-loss-in-adults-with-obesity-or-overweight-in-surmount-1--301534871.html",
        7.6,
        W,
        False,
        "PR Newswire timestamp 06:15 ET.",
    ),
    (
        "LLY-20220513-mounjaro-us",
        "LLY",
        "NVO",
        "regulatory",
        "Mounjaro approved by the FDA for type 2 diabetes",
        local(2022, 5, 13, 17, 54, ET),
        "exact",
        "press_release",
        PRN
        + "fda-approves-lillys-mounjaro-tirzepatide-injection-the-first-and-only-gip-and-glp-1-receptor-agonist-for-the-treatment-of-adults-with-type-2-diabetes-301547339.html",
        None,
        "",
        False,
        "PR Newswire timestamp 17:54 ET.",
    ),
    (
        "LLY-20231108-zepbound-us",
        "LLY",
        "NVO",
        "regulatory",
        "Zepbound approved by the FDA for chronic weight management",
        local(2023, 11, 8, 12, 22, ET),
        "exact",
        "press_release",
        PRN
        + "fda-approves-lillys-zepbound-tirzepatide-for-chronic-weight-management-a-powerful-new-option-for-the-treatment-of-obesity-or-overweight-with-weight-related-medical-problems-301982041.html",
        None,
        "",
        False,
        "PR Newswire timestamp 12:22 ET, during the US session.",
    ),
    (
        "LLY-20240417-surmount-osa",
        "LLY",
        "NVO;RMD",
        "trial_readout",
        "SURMOUNT-OSA: tirzepatide cuts sleep apnea severity by up to 63%",
        local(2024, 4, 17, 6, 15, ET),
        "exact",
        "press_release",
        PRN
        + "tirzepatide-reduced-sleep-apnea-severity-by-up-to-nearly-two-thirds-in-adults-with-obstructive-sleep-apnea-osa-and-obesity-302118929.html",
        None,
        "",
        False,
        "PR Newswire timestamp 06:15 ET. A read-through event for ResMed.",
    ),
    (
        "LLY-20241204-surmount5",
        "LLY",
        "NVO",
        "trial_readout",
        "SURMOUNT-5: Zepbound beats Wegovy head-to-head, 20.2% vs 13.7%",
        local(2024, 12, 4, 6, 45, ET),
        "exact",
        "press_release",
        PRN
        + "lillys-zepbound-tirzepatide-superior-to-wegovy-semaglutide-in-head-to-head-trial-showing-an-average-weight-loss-of-20-2-vs-13-7-302322351.html",
        6.5,
        H2H,
        False,
        "PR Newswire timestamp 06:45 ET.",
    ),
    (
        "LLY-20250417-achieve1",
        "LLY",
        "NVO",
        "trial_readout",
        "ACHIEVE-1: orforglipron, first phase 3 oral GLP-1 readout, in type 2 diabetes",
        local(2025, 4, 17, 6, 45, ET),
        "exact",
        "press_release",
        PRN
        + "lillys-oral-glp-1-orforglipron-demonstrated-statistically-significant-efficacy-results-and-a-safety-profile-consistent-with-injectable-glp-1-medicines-in-successful-phase-3-trial-302430985.html",
        None,
        "",
        False,
        "PR Newswire timestamp 06:45 ET.",
    ),
    (
        "LLY-20250807-attain1",
        "LLY",
        "NVO",
        "trial_readout",
        "ATTAIN-1: orforglipron 12.4% weight loss in obesity",
        local(2025, 8, 7, 6, 25, ET),
        "exact",
        "press_release",
        PRN
        + "lillys-oral-glp-1--orforglipron-delivers-weight-loss-of-up-to-an-average-of-27-3-lbs-in-first-of-two-pivotal-phase-3-trials-in-adults-with-obesity-302523649.html",
        -10.3,
        W,
        True,
        "PR Newswire timestamp 06:25 ET; Lilly reported Q2 earnings the same morning.",
    ),
    (
        "LLY-20251106-us-pricing-deal",
        "LLY",
        "NVO;HIMS",
        "pricing_policy",
        "Lilly and the US government agree to expand access to obesity medicines",
        local(2025, 11, 6, 13, 54, ET),
        "exact",
        "press_release",
        PRN
        + "lilly-and-us-government-agree-to-expand-access-to-obesity-medicines-to-millions-of-americans-302607652.html",
        None,
        "",
        True,
        "PR Newswire timestamp 13:54 ET. Novo announced a parallel agreement (see its row).",
    ),
    (
        "LLY-20251211-triumph4",
        "LLY",
        "NVO",
        "trial_readout",
        "TRIUMPH-4: retatrutide 28.7% weight loss with knee osteoarthritis",
        local(2025, 12, 11, 6, 45, ET),
        "exact",
        "press_release",
        PRN
        + "lillys-triple-agonist-retatrutide-delivered-weight-loss-of-up-to-an-average-of-71-2-lbs-along-with-substantial-relief-from-osteoarthritis-pain-in-first-successful-phase-3-trial-302638804.html",
        6.0,
        W,
        False,
        "PR Newswire timestamp 06:45 ET.",
    ),
    (
        "LLY-20260401-foundayo-us",
        "LLY",
        "NVO",
        "regulatory",
        "Foundayo (orforglipron) approved by the FDA for weight loss",
        local(2026, 4, 1, 11, 30, ET),
        "exact",
        "press_release",
        PRN
        + "fda-approves-lillys-foundayo-orforglipron-the-only-glp-1-pill-for-weight-loss-that-can-be-taken-any-time-of-day-without-food-or-water-restrictions-302731485.html",
        None,
        "",
        False,
        "PR Newswire timestamp 11:30 ET.",
    ),
    # Date known, time not (or only "before the open" is known). timing upper_bound.
    (
        "AMGN-20241126-maritide-ph2",
        "AMGN",
        "LLY;NVO",
        "trial_readout",
        "MariTide phase 2: about 20% weight loss at 52 weeks",
        day_end(2024, 11, 26, ET),
        "upper_bound",
        "media",
        "https://pharmaphorum.com/news/amgens-big-reveal-obesity-data-falls-bit-flat",
        None,
        "",
        False,
        "Release time not captured; the date is from press coverage. Amgen release: https://www.amgen.com/newsroom/press-releases/2024/11/amgen-announces-robust-weight-loss-with-maritide-in-people-living-with-obesity-or-overweight-at-52-weeks-in-a-phase-2-study",
    ),
    (
        "PFE-20250414-danuglipron-stop",
        "PFE",
        "LLY;NVO",
        "competitor",
        "Pfizer ends development of oral GLP-1 danuglipron",
        day_end(2025, 4, 14, ET),
        "upper_bound",
        "media",
        "https://www.businessday.co.za/bd/companies/2025-04-14-pfizer-ends-development-of-weight-loss-pill/",
        None,
        "",
        False,
        "Release time not captured; the date is from press coverage (businessday, 2025-04-14).",
    ),
    (
        "PFE-20250922-metsera",
        "PFE",
        "LLY;NVO",
        "mna_licensing",
        "Pfizer to acquire Metsera for $4.9bn",
        day_end(2025, 9, 22, ET),
        "upper_bound",
        "media",
        "https://www.businesswire.com/news/home/20250922965053/en/Pfizer-to-Acquire-Metsera-and-its-Next-Generation-Obesity-Portfolio",
        None,
        "",
        False,
        "Release time not captured; the date is from the Business Wire release and press coverage.",
    ),
    (
        "HIMS-20250623-novo-ends-deal",
        "HIMS",
        "NVO",
        "mna_licensing",
        "Novo Nordisk ends its Wegovy partnership with Hims & Hers",
        day_end(2025, 6, 23, ET),
        "upper_bound",
        "media",
        "https://qz.com/novo-nordisk-hims-hers-ozempic-wegovy-weight-loss-drugs",
        None,
        "",
        False,
        "Date from press coverage and Novo's 23 June release; time not captured. Hims and Novo trade in different time zones, so the window covers both.",
    ),
    (
        "RHHBY-20231204-carmot",
        "RHHBY",
        "LLY;NVO",
        "mna_licensing",
        "Roche to acquire Carmot Therapeutics for $2.7bn",
        day_end(2023, 12, 4, CET),
        "upper_bound",
        "press_release",
        "https://assets.roche.com/f/176343/55c0bf991e/01-04122023_mr_roche-acquires-carmot-therapeutics_en.pdf",
        None,
        "",
        False,
        "Release time not shown on the PDF.",
    ),
    (
        "LLY-20241002-tirzepatide-shortage-over",
        "LLY",
        "NVO;HIMS",
        "supply",
        "FDA declares the tirzepatide shortage resolved",
        day_end(2024, 10, 2, ET),
        "upper_bound",
        "regulator",
        "https://www.foley.com/insights/publications/2024/10/fda-removes-lillys-zepbound-mounjaro-tirzepatide-injection-drug-shortage-list/",
        None,
        "",
        False,
        "FDA shortage database update; time not published. The FDA reaffirmed the decision on 2024-12-19.",
    ),
    (
        "NVO-20250221-semaglutide-shortage-over",
        "NVO",
        "LLY;HIMS",
        "supply",
        "FDA declares the semaglutide shortage resolved",
        day_end(2025, 2, 21, ET),
        "upper_bound",
        "regulator",
        "https://www.fiercehealthcare.com/health-tech/fda-declares-semaglutide-shortage-over-spelling-end-compounded-glp-1-market",
        None,
        "",
        False,
        "FDA shortage database update; time not published. Compounders were given until 22 April / 22 May 2025.",
    ),
    (
        "NVO-20250117-cms-negotiation-list",
        "NVO",
        "LLY",
        "pricing_policy",
        "CMS selects semaglutide for Medicare price negotiation",
        day_end(2025, 1, 17, ET),
        "upper_bound",
        "regulator",
        "https://www.healthcaredive.com/news/medicare-drug-price-negotiations-second-round-semaglutide/737662/",
        None,
        "",
        False,
        "CMS announced the 15 round 2 drugs on 17 January 2025 (benefitspro, 2025-01-17); negotiated prices take effect 2027-01-01. Time not published.",
    ),
    (
        "NVO-20240111-fda-suicidal-ideation",
        "NVO",
        "LLY",
        "safety",
        "FDA finds no evidence that GLP-1 drugs cause suicidal thoughts (preliminary)",
        day_end(2024, 1, 11, ET),
        "upper_bound",
        "regulator",
        "https://www.fda.gov/drugs/fda-drug-safety-podcasts/update-fdas-ongoing-evaluation-reports-suicidal-thoughts-or-actions-patients-taking-certain-type",
        None,
        "",
        False,
        "FDA drug safety communication dated 2024-01-11; time not published. Resolves an open safety question, so the sign of the reaction is not obvious.",
    ),
    (
        "LLY-20241126-medicare-obesity-proposal",
        "LLY",
        "NVO;HIMS",
        "pricing_policy",
        "Biden administration proposes Medicare and Medicaid coverage of obesity drugs",
        day_end(2024, 11, 26, ET),
        "upper_bound",
        "media",
        "https://newschannel9.com/news/nation-world/biden-administration-proposes-medicare-medicaid-coverage-for-costly-weight-loss-drugs-wegovy-ozempic-department-of-health-and-human-services-pharmaceutical-industry-robert-f-kennedy-jr-nominee-obese-americans",
        None,
        "",
        True,
        "Same day as Amgen's MariTide data.",
    ),
]


# (accession, ticker, also, type, slug, title, surprise, basis, confounded, notes)
OTHERS = [
    (
        "0000950170-24-020616",
        "VKTX",
        "LLY;NVO",
        "trial_readout",
        "vk2735-ph2",
        "VK2735 phase 2 VENTURE: positive top-line weight loss",
        None,
        "",
        False,
        "Filed 07:04 ET, before the open.",
    ),
    (
        "0001607678-25-000003",
        "VKTX",
        "LLY;NVO",
        "trial_readout",
        "vk2735-oral-ph2",
        "VK2735 oral phase 2 VENTURE-Oral top-line results",
        None,
        "",
        False,
        "Filed 07:09 ET, before the open.",
    ),
    (
        "0001193125-26-397219",
        "VKTX",
        "LLY;NVO",
        "trial_readout",
        "vk2735-maintenance",
        "VK2735 maintenance study top-line results",
        None,
        "",
        False,
        "Filed 07:06 ET, before the open.",
    ),
    (
        "0001193125-23-061389",
        "WW",
        "LLY;NVO",
        "mna_licensing",
        "sequence",
        "WeightWatchers agrees to acquire Sequence, a GLP-1 telehealth platform",
        None,
        "",
        True,
        "Announced with Q4 2022 results. Filed after the close.",
    ),
    (
        "0001773751-26-000033",
        "HIMS",
        "NVO;LLY",
        "mna_licensing",
        "us-weight-loss-shift",
        "Hims & Hers announces a strategic shift for its US weight loss business",
        None,
        "",
        False,
        "Press release dated 9 March 2026; the 8-K was filed on the 11th, after the close.",
    ),
]


STATED = {"0001773751-26-000033": date(2026, 3, 9)}  # date printed in the press release


def others_frame() -> pl.DataFrame:
    df = pl.read_parquet("data/processed/edgar_others.parquet")
    by_acc = {r["accession"]: r for r in df.iter_rows(named=True)}
    rows = []
    for acc, tk, also, et, slug, title, sur, basis, conf, notes in OTHERS:
        r = by_acc[acc]
        sd = STATED.get(acc, r["filing_date"])
        rows.append(
            {
                "event_id": f"{tk}-{sd:%Y%m%d}-{slug}",
                "ticker": tk,
                "also_affects": also,
                "event_type": et,
                "title": title,
                "occurred_at": r["accepted_at"],
                "timing": "upper_bound",
                "stated_date": sd,
                "timestamp_source": "edgar_acceptance",
                "source_url": f"https://www.sec.gov/Archives/edgar/data/{r['cik']}/{acc.replace('-', '')}/{acc}-index.htm",
                "scheduled": False,
                "announced_on": None,
                "surprise": sur,
                "surprise_basis": basis,
                "confounded": conf,
                "verified_on": TODAY,
                "notes": notes,
            }
        )
    return pl.DataFrame(rows, schema=ledger.SCHEMA)


def manual_frame() -> pl.DataFrame:
    rows = []
    for eid, tk, also, et, title, at, timing, src, url, sur, basis, conf, notes in MANUAL:
        rows.append(
            {
                "event_id": eid,
                "ticker": tk,
                "also_affects": also,
                "event_type": et,
                "title": title,
                "occurred_at": at,
                "timing": timing,
                "stated_date": at.astimezone(CET if tk == "RHHBY" else ET).date(),
                "timestamp_source": src,
                "source_url": url,
                "scheduled": False,
                "announced_on": None,
                "surprise": sur,
                "surprise_basis": basis,
                "confounded": conf,
                "verified_on": TODAY,
                "notes": notes,
            }
        )
    return pl.DataFrame(rows, schema=ledger.SCHEMA)


def main() -> None:
    make_edgar_rows.main()
    df = pl.read_csv(
        "data/ledger/catalysts.csv", schema_overrides=ledger.SCHEMA, try_parse_dates=True
    )
    for eid, fields in OVERRIDES.items():
        if eid not in df["event_id"].to_list():
            raise SystemExit(f"override for unknown event {eid}")
        for col, val in fields.items():
            df = df.with_columns(
                pl.when(pl.col("event_id") == eid)
                .then(pl.lit(val))
                .otherwise(pl.col(col))
                .alias(col)
            )
    out = pl.concat([df, manual_frame(), others_frame()]).sort("occurred_at")
    out = out.with_columns(
        confounded=pl.Series(ledger.derive_confounded(out)) | pl.col("confounded")
    )
    problems = ledger.validate(out)
    if problems:
        raise SystemExit("\n".join(problems))
    out.write_csv("data/ledger/catalysts.csv")
    print(out.height, "events written")


if __name__ == "__main__":
    main()
