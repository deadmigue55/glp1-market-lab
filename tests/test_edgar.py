from datetime import UTC, date, datetime

from glp1.ingest import edgar

RECENT = {
    "accessionNumber": ["0000059478-24-000001", "0000059478-24-000002", "0000059478-24-000003"],
    "form": ["8-K", "10-Q", "8-K"],
    "filingDate": ["2024-08-08", "2024-08-09", "2024-08-01"],
    "acceptanceDateTime": [
        "2024-08-08T10:47:50.000Z",
        "2024-08-09T11:00:00.000Z",
        "2024-08-01T20:30:00.000Z",
    ],
    "items": ["2.02,9.01", "", "7.01"],
    "primaryDocument": ["a.htm", "b.htm", "c.htm"],
}


def test_parse_submissions_keeps_only_8k_and_6k_and_sorts_by_acceptance():
    df = edgar.parse_submissions(59478, [{"filings": {"recent": RECENT}}])
    assert df["form"].to_list() == ["8-K", "8-K"]
    assert df["accession"].to_list() == ["0000059478-24-000003", "0000059478-24-000001"]
    assert df["accepted_at"][1] == datetime(2024, 8, 8, 10, 47, 50, tzinfo=UTC)
    assert df["filing_date"][1] == date(2024, 8, 8)


def test_parse_submissions_reads_older_file_blocks_and_dedupes():
    older = dict(RECENT)  # an older-files page has no "filings" wrapper
    df = edgar.parse_submissions(59478, [{"filings": {"recent": RECENT}}, older])
    assert df.height == 2


INDEX = """
<table><tr><td>1</td><td>8-K</td><td><a href="/Archives/x/a.htm">a.htm</a></td><td>8-K</td></tr>
<tr><td>2</td><td>PR</td><td><a href="/Archives/x/ex99.htm">ex99.htm</a></td><td>EX-99.1</td></tr></table>
"""


def test_pick_document_prefers_the_press_release_exhibit():
    assert edgar.pick_document(INDEX, "a.htm") == "ex99.htm"
    assert edgar.pick_document("<table></table>", "a.htm") == "a.htm"


def test_lead_text_strips_markup_scripts_and_entities():
    markup = "<html><script>var x=1;</script><body><p>Lilly&nbsp;reports</p><p>results</p></body>"
    assert edgar.lead_text(markup) == "Lilly reports results"
    assert len(edgar.lead_text("<p>" + "word " * 2000 + "</p>", limit=50)) == 50
