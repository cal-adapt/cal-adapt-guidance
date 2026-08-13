#!/usr/bin/env python3
"""
Edit reference-library-data.csv to add, remove, or re-categorize references
— do not edit reference-library-data.js directly, it is generated.

The "category" column supports multiple topics per reference: separate them
with a semicolon, e.g. "WRF; Bias Correction".

The "pdf" column is optional: a path relative to this page (e.g.
../assets/pdfs/some-file.pdf) to a PDF hosted on this site. When set, the
table's link button points to that PDF and reads "View" instead of "Link".
Use a relative path, not a root-relative ("/assets/...") one — the site is
served from a subpath on GitHub Pages, so a root-relative path 404s there.

Otherwise, the table's link button points to the "url" (or "doi") field on
the entry in references.bib. If a source has neither, add its url to the
Zotero record and re-export references.bib — this script errors rather than
falling back to a link hardcoded in the CSV.

Citation text is formatted from references.bib via Quarto's bundled pandoc
citeproc, using the site's citation-style.csl, so it matches the citation
style used everywhere else on the site.

Run from anywhere: python3 general-resources/reference-library/generate-reference-library.py
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
BIB_PATH = os.path.join(ROOT_DIR, "references.bib")
CSL_PATH = os.path.join(ROOT_DIR, "citation-style.csl")
CSV_PATH = os.path.join(SCRIPT_DIR, "reference-library-data.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "reference-library-data.js")

with open(CSV_PATH, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

with open(BIB_PATH, encoding="utf-8") as f:
    bib_text = f.read()


def extract_bib_fields(key):
    m = re.search(r"@(\w+)\{" + re.escape(key) + r",\n(.*?)\n\}\n", bib_text, re.DOTALL)
    if not m:
        sys.exit(f"error: citekey '{key}' (from reference-library-data.csv) not found in references.bib")
    body = m.group(2)
    return dict(re.findall(r"^\s*(\w+)\s*=\s*\{?(.*?)\}?,?$", body, re.MULTILINE))


# ── format citations via pandoc citeproc, using the site's CSL ──────────────
keys = [row["key"] for row in rows]
with tempfile.TemporaryDirectory() as tmp:
    md_path = os.path.join(tmp, "refs.md")
    html_path = os.path.join(tmp, "refs.html")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"bibliography: {BIB_PATH}\n")
        f.write(f"csl: {CSL_PATH}\n")
        f.write("nocite: |\n")
        f.write("  " + ", ".join(f"@{k}" for k in keys) + "\n")
        f.write("---\n")

    subprocess.run(
        ["quarto", "pandoc", md_path, "--citeproc", "--to=html5", "--wrap=none", "-o", html_path],
        check=True,
        cwd=ROOT_DIR,
    )
    with open(html_path, encoding="utf-8") as f:
        citeproc_html = f.read()

citation_by_key = {}
for m in re.finditer(
    r'<div id="ref-(.+?)" class="csl-entry"[^>]*>.*?<div class="csl-right-inline">(.*?)</div>\s*</div>',
    citeproc_html,
    re.DOTALL,
):
    citation = re.sub(r"\s+", " ", m.group(2)).strip()
    # The CSL appends the source URL/DOI as a clickable link; each row already
    # has its own Link/View button, so drop the hyperlink but keep the DOI/URL
    # text itself as part of the citation.
    citation = re.sub(
        r'\s*<a href="[^"]*">([^<]*)</a>\.?\s*$',
        lambda m: " " + m.group(1).rstrip(".") + ".",
        citation,
    ).rstrip()
    if not citation.endswith("."):
        citation += "."
    citation_by_key[m.group(1)] = citation

# ── assemble table data ──────────────────────────────────────────────────────
data = []
for row in rows:
    key = row["key"]
    fields = extract_bib_fields(key)
    pdf = row.get("pdf")
    is_pdf = bool(pdf)
    link = pdf or fields.get("url") or (
        f"https://doi.org/{fields['doi']}" if fields.get("doi") else ""
    )
    if not link:
        sys.exit(
            f"error: '{key}' has no url/doi in references.bib and no pdf in "
            "reference-library-data.csv — add a url to the source in Zotero"
        )
    citation = citation_by_key.get(key)
    if not citation:
        sys.exit(f"error: pandoc citeproc did not return an entry for '{key}'")
    categories = [c.strip() for c in row["category"].split(";") if c.strip()]
    data.append(
        {
            "categories": categories,
            "description": row["description"],
            "citation": citation,
            "link": link,
            "isPdf": is_pdf,
        }
    )

data.sort(key=lambda d: (0 if "Cal-Adapt" in d["categories"] else 1, d["categories"][0], d["description"]))

js_data = json.dumps(data, ensure_ascii=False, indent=2)
js = f"""// Auto-generated from reference-library-data.csv and references.bib — do not edit
var REFERENCES_DATA = {js_data};
"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(js)

print(f"Generated {os.path.relpath(OUT_PATH, ROOT_DIR)} from {len(data)} references")
