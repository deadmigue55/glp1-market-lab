"""Keeps the written study, the findings register and the detailed documents in step.

Same idea as the numbers-in-docs tests of each step: a claim cannot drift away from its evidence.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def text(name: str) -> str:
    return " ".join((DOCS / name).read_text(encoding="utf-8").split())


def register() -> list[list[str]]:
    rows = []
    for line in (DOCS / "findings.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.fullmatch(r"F\d+", cells[0]):
            rows.append(cells)
    return rows


def test_every_register_row_has_evidence_and_a_checking_test():
    rows = register()
    assert [r[0] for r in rows] == [f"F{i}" for i in range(1, len(rows) + 1)]
    for fid, _claim, strength, evidence, check in rows:
        assert strength.split(" ")[0] in {
            "robust",
            "suggestive",
            "exploratory",
            "not",
            "mechanism",
        }, fid
        for path in [p.strip() for p in evidence.split(",")] + [check]:
            assert (ROOT / path).exists(), (fid, path)


def test_study_and_register_mention_the_same_findings():
    ids_in_study = set(re.findall(r"\bF(\d+)\b", text("study.md")))
    expected = {str(i) for i in range(1, len(register()) + 1)}
    assert ids_in_study == expected


def test_study_numbers_appear_in_the_documents_that_are_tied_to_results():
    pairs = {
        "event-study.md": [
            "Lilly earnings 1.75 (p = 0.009)",
            "Novo earnings 1.64 (p = 0.008)",
            "Novo earnings fall to 1.06 (p = 0.146)",
            "2.9 pp per 1%",
        ],
        "ecosystem.md": ["-10.5% (1.8)", "-19.3% (3.6)", "0.078 (p = 0.100)", "12.1%", "16.5%"],
        "valuation.md": ["$479bn (280-894)", "$49.5bn", "22.0%"],
        "attention.md": ["p = 0.002"],
        "forecast.md": ["49% and 51%", "one passes the decision rule", "0.025", "0.078", "0.057"],
    }
    study = text("study.md").replace("2212", "-")
    for doc, snippets in pairs.items():
        src = text(doc)
        for s in snippets:
            assert s in src, (doc, s)
    for s in [
        "Lilly earnings 1.75 (p = 0.009)",
        "Novo earnings 1.64 (p = 0.008)",
        "Novo earnings fall to 1.06 (p = 0.146)",
        "2.9 pp per 1%",
        "-10.5% (1.8)",
        "-19.3% (3.6)",
        "0.078 (p = 0.100)",
        "$479bn (280-894)",
        "$49.5bn",
        "22.0%",
        "p = 0.002",
        "0.025",
        "0.078",
        "0.057",
    ]:
        assert s in study, s


def test_every_public_document_carries_the_disclaimer_and_no_advice_language():
    for name in (
        "study.md",
        "findings.md",
        "model-card.md",
        "forecast.md",
        "nightly.md",
        "event-study.md",
        "ecosystem.md",
        "valuation.md",
        "attention.md",
    ):
        assert "not investment advice" in text(name).lower(), name
    advice = re.compile(r"\b(you should (buy|sell)|buy rating|sell rating|price target)\b", re.I)
    sources = list(DOCS.glob("*.md")) + list((ROOT / "site" / "src").glob("*.jsx"))
    for f in sources:
        if f.name in {"plan.md", "research.md"}:
            continue
        assert not advice.search(f.read_text(encoding="utf-8")), f.name
    assert "Not investment advice" in (ROOT / "site" / "src" / "App.jsx").read_text(
        encoding="utf-8"
    )
