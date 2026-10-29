"""Browser checks of the live page (Chromium via Playwright).

Build and serve first (npm run build && npx vite preview --port 4174), then:
    uv run --no-project --with playwright python -I scripts/qa.py [http://localhost:4174] [shots-dir]

Checks behaviour, not just looks: no console errors, the fan renders, choosing an earnings outcome or
an FDA result moves the forecast the right way, no horizontal overflow on a phone, both themes, and an
axe-core accessibility scan with zero violations.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4174"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("qa-shots")
OUT.mkdir(parents=True, exist_ok=True)
AXE = Path(__file__).resolve().parents[1] / "node_modules" / "axe-core" / "axe.min.js"
failed = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not ok:
        failed.append(name)


def middle(page):
    """The 'middle outcome' price shown in the readout, as a number."""
    txt = page.locator(".readout div").nth(1).locator("b").inner_text()
    return float(re.sub(r"[^0-9.]", "", txt))


def settle(page):
    page.wait_for_function("document.querySelector('.readout') !== null")
    page.wait_for_timeout(400)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE)
    settle(page)

    check("fan chart renders", page.locator("svg[role=img]").count() >= 3)
    check(
        "four sections",
        all(page.locator(f"#{s}").count() for s in ("forecast", "news", "value", "record")),
    )
    page.screenshot(path=str(OUT / "01-forecast-light.png"), full_page=False)

    # earnings: cut < model mix < raised, and the chart follows
    page.get_by_label("Model mix").check()
    settle(page)
    base = middle(page)
    page.locator("input[name=earn]").nth(1).check(force=True)  # raised
    settle(page)
    raised = middle(page)
    page.locator("input[name=earn]").nth(3).check(force=True)  # cut
    settle(page)
    cut = middle(page)
    check(
        "raised guidance lifts the middle outcome, cut lowers it",
        cut < base < raised,
        f"{cut} < {base} < {raised}",
    )
    page.locator("input[name=earn]").nth(0).check(force=True)
    settle(page)

    # horizon slider
    page.locator("#hz").fill("2")
    settle(page)
    check(
        "slider changes the readout label",
        "trading days ahead" in page.locator("label[for=hz]").inner_text(),
    )

    # Novo: approval beats rejection
    page.get_by_role("button", name="Novo Nordisk").click()
    settle(page)
    page.locator("input[name=pick]").nth(1).check(force=True)
    settle(page)
    approved = middle(page)
    page.locator("input[name=pick]").nth(2).check(force=True)
    settle(page)
    rejected = middle(page)
    check("FDA approval beats rejection", approved > rejected, f"{approved} > {rejected}")
    page.screenshot(path=str(OUT / "02-novo-scenario.png"), full_page=False)
    page.get_by_role("button", name="Reset to the model").click()

    page.locator("#record").scroll_into_view_if_needed()
    page.screenshot(path=str(OUT / "03-full-light.png"), full_page=True)

    # themes and axe
    for theme in ("light", "dark"):
        page.evaluate(f"document.documentElement.dataset.theme = '{theme}'")
        page.wait_for_timeout(200)
        page.add_script_tag(path=str(AXE))
        res = page.evaluate(
            "axe.run().then(r => r.violations.map(v => v.id + ': ' + v.nodes.length + ' ' + v.nodes[0].html.slice(0, 120)))"
        )
        check(f"axe: no violations ({theme})", not res, "; ".join(res))
        if theme == "dark":
            page.screenshot(path=str(OUT / "04-full-dark.png"), full_page=True)

    # phone width
    phone = browser.new_page(viewport={"width": 390, "height": 800})
    phone.goto(BASE)
    settle(phone)
    check(
        "no horizontal overflow on a phone",
        phone.evaluate("document.documentElement.scrollWidth <= window.innerWidth"),
        str(phone.evaluate("document.documentElement.scrollWidth")),
    )
    phone.screenshot(path=str(OUT / "05-phone.png"), full_page=False)

    check("no console errors", not errors, "; ".join(errors[:3]))
    browser.close()

print(f"\n{len(failed)} failed" if failed else "\nall passed")
sys.exit(1 if failed else 0)
