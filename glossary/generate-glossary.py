#!/usr/bin/env python3
"""
Edit glossary-data.json to add or update terms — do not edit the generated files directly.
Run from anywhere: python3 glossary/generate-glossary.py
"""
import json
import re
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(SCRIPT_DIR, "glossary-data.json"), encoding="utf-8") as f:
    terms = json.load(f)


def sort_key(t):
    first = t["term"][0]
    # Numbers sort before letters
    return ("0" if first.isdigit() else first.upper(), t["term"].lower())


terms_sorted = sorted(terms, key=sort_key)

# ── generate _glossary-generated.qmd ────────────────────────────────────────
lines = []
for t in terms_sorted:
    lines.append(f'## {t["term"]} {{#{t["slug"]}}}')
    lines.append("")
    lines.append(t["definition"])
    lines.append("")

with open(os.path.join(SCRIPT_DIR, "_glossary-generated.qmd"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))


# ── strip markdown for tooltip text ─────────────────────────────────────────
def to_tooltip(definition):
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", definition)   # [text](url) → text
    text = re.sub(r"\[([^\]]+)\]", r"\1", text)                   # [text] → text
    text = text.strip()
    return text[:200].rstrip() + ("..." if len(text) > 200 else "")


tooltip_map = {t["slug"]: to_tooltip(t["definition"]) for t in terms_sorted}

# ── generate _glossary-tooltip-inline.html ───────────────────────────────────
js_data = json.dumps(tooltip_map, ensure_ascii=False, indent=2)

html = f"""<!-- Auto-generated from glossary-data.json — do not edit -->
<script>
(function () {{
  var GLOSSARY = {js_data};

  function initTooltips() {{
    if (window.location.pathname.match(/glossary/)) return;
    document.querySelectorAll("a[href]").forEach(function (link) {{
      var href = link.getAttribute("href");
      var m = href && href.match(/glossary[^#]*#([\\w-]+)/);
      if (!m) return;
      var def = GLOSSARY[m[1]];
      if (!def) return;
      link.setAttribute("data-bs-toggle", "tooltip");
      link.setAttribute("data-bs-placement", "top");
      link.setAttribute("title", def);
    }});
    if (typeof bootstrap !== "undefined") {{
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {{
        new bootstrap.Tooltip(el, {{ trigger: "hover focus" }});
      }});
    }}
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", initTooltips);
  }} else {{
    initTooltips();
  }}
}})();
</script>
"""

with open(os.path.join(SCRIPT_DIR, "_glossary-tooltip-inline.html"), "w", encoding="utf-8") as f:
    f.write(html)

print("Generated _glossary-generated.qmd and _glossary-tooltip-inline.html")
