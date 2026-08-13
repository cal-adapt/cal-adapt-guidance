# Cal-Adapt Guidance Website

[![Deploy to GitHub Pages](https://github.com/cal-adapt/cal-adapt-guidance/actions/workflows/gh-pages.yml/badge.svg)](https://github.com/cal-adapt/cal-adapt-guidance/actions/workflows/gh-pages.yml)
[![Check Links](https://github.com/cal-adapt/cal-adapt-guidance/actions/workflows/check-links.yml/badge.svg)](https://github.com/cal-adapt/cal-adapt-guidance/actions/workflows/check-links.yml)

[Quarto](https://quarto.org/) source for the Cal-Adapt: Analytics Engine guidance site, deployed at [analytics.cal-adapt.org](https://analytics.cal-adapt.org). Includes guidance pages, a blog, and a glossary, each built to both HTML and PDF.

## Local development

Install [Quarto](https://quarto.org/docs/get-started/). Some pages use Mermaid diagrams which require a headless browser for PDF rendering. Install it once with:

```bash
quarto install chrome-headless-shell
```

Then run:

```bash
quarto preview
```

This starts a local dev server with live reload at `http://localhost:4200`.

To build the site without previewing:

```bash
quarto render
```

Output is written to `_site/`.

## Documentation

For everything beyond local dev (citations/Zotero, the glossary, figures, deployment, and writing a blog post), see the [wiki](https://github.com/cal-adapt/cal-adapt-guidance/wiki). Start on its Home page if you're new to the repo.

## Contributors

[![Contributors](https://contrib.rocks/image?repo=cal-adapt/cal-adapt-guidance)](https://github.com/cal-adapt/cal-adapt-guidance/graphs/contributors)
