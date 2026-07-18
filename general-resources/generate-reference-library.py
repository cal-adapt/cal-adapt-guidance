#!/usr/bin/env python3
"""
Edit reference-library-data.csv to add, remove, or re-categorize references
— do not edit _reference-library-data.html directly, it is generated.

The "category" column supports multiple topics per reference: separate them
with a semicolon, e.g. "WRF; Bias Correction".

The "pdf" column is optional: a root-relative path (e.g.
/assets/pdfs/some-file.pdf) to a PDF hosted on this site. When set, the
table's link button points to that PDF and reads "View" instead of "Link".

Citation text is formatted from references.bib via Quarto's bundled pandoc
citeproc, using the site's citation-style.csl, so it matches the citation
style used everywhere else on the site.

Run from anywhere: python3 general-resources/generate-reference-library.py
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
BIB_PATH = os.path.join(ROOT_DIR, "references.bib")
CSL_PATH = os.path.join(ROOT_DIR, "citation-style.csl")
CSV_PATH = os.path.join(SCRIPT_DIR, "reference-library-data.csv")
OUT_PATH = os.path.join(SCRIPT_DIR, "_reference-library-data.html")

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
    # The CSL appends the source URL/DOI as a clickable link; drop it here since
    # each row already has its own Link/View button.
    citation = re.sub(r'\s*<a href="[^"]*">[^<]*</a>\.?\s*$', "", citation).rstrip()
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
    link = pdf or row.get("link") or fields.get("url") or (
        f"https://doi.org/{fields['doi']}" if fields.get("doi") else ""
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
html = f"""<!-- Auto-generated from reference-library-data.csv and references.bib — do not edit -->
<script>
var REFERENCES_DATA = {js_data};
</script>
"""

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Generated {os.path.relpath(OUT_PATH, ROOT_DIR)} from {len(data)} references")
