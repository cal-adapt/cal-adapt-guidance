# caladapt-guidance-test

Testing site for AE guidance website migration to a new framework using Quarto, with support for search and a blog :)

## Local development

Install [Quarto](https://quarto.org/docs/get-started/). Some pages use Mermaid diagrams which require a headless browser for PDF rendering — install it once with:

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

## Deployment

The site deploys automatically to Netlify via GitHub Actions (`.github/workflows/deploy.yml`):

- **Push to `main`** → deploys to production
- **Open a PR** → Netlify builds a preview URL and posts it as a comment on the PR

The production URL is posted in the GitHub Actions deploy step output (click the workflow run → `Deploy to Netlify` step to find the URL).

## Glossary

All glossary terms and tooltip definitions live in `glossary/glossary-data.json` — that's the only file you need to edit.

To add or update a term, edit the JSON. The generate script runs automatically on every `quarto render` or `quarto preview` (via the `pre-render` hook in `_quarto.yml`), so no manual step is needed — just edit and build.

To link to a glossary term from any page (includes a hover tooltip):

```markdown
[model run](/glossary/index.qmd#model-run)
```

The `slug` for each term is defined in `glossary-data.json`.

## Figures

Each page with figures gets its own `figures/html/` and `figures/static/` subdirectory alongside the `.qmd` file:

- `figures/html/<filename>.html` — interactive Panel/Bokeh/Plotly figure, embedded in HTML output
- `figures/static/<filename>.png` — static image, used as the PDF fallback and the mobile fallback

Declare `resources: - figures/html/` in the page's frontmatter so Quarto copies the files to `_site/`.

### Standard figure block

```
::: {.content-visible when-format="html"}
```{=html}
<div class="figure-container d-none d-md-block">
{{< include figures/html/<filename>.html >}}
</div>
```
![](figures/static/<filename>.png){.d-md-none fig-alt="..."}
:::
::: {.content-visible when-format="pdf"}
![](figures/static/<filename>.png){fig-alt="..."}
:::
```

- `d-none d-md-block` on the interactive figure hides it below the `md` breakpoint (768px, matching the mobile breakpoint in `styles.css`).
- `d-md-none` on the mobile image shows it only below that breakpoint, so phones get the static PNG instead of a cramped/JS-heavy interactive figure.
- This mobile swap only applies to charts and maps — interactive data tables are left as scrollable HTML on mobile, since a flattened table image would have unreadably small text.

For true `<iframe src="...">` embeds (rather than `{{< include >}}`), add the same `d-none d-md-block` class directly to the `<iframe>` tag instead of a wrapping `<div>`.

Use iframes (not `{{< include >}}`) for Panel/HoloViz figures when more than one appears on a page — bundling multiple Panel figures via `{{< include >}}` causes JS conflicts between them.

### Notes

- Only the *first* figure on a page can safely use the `{#fig-...}` wrapper with cross-references (`@fig-...`). Additional figures with the same pattern trigger a Quarto "FloatRefTarget with no content" bug that breaks the embed — for those, drop the `{#fig-...}` wrapper and caption manually ("Figure 2.").
- `<iframe>` has no `alt` attribute — set its `title` to the same text as the corresponding `fig-alt`, so HTML and PDF carry equivalent accessible descriptions.
- Run `make preview` from the project root to render and serve the full site locally (`quarto render` + a static server on `_site/`). `quarto preview` alone only serves pages with recent changes, which can hide stale figures.

## Link checking

A link checker runs automatically on every push to `main` and every Monday at 8am UTC (`.github/workflows/check-links.yml`). It renders the site and uses [lychee](https://github.com/lycheeverse/lychee) to check all HTML links, failing the workflow if any broken links are found.

### Setup

Two GitHub Actions secrets are required:

| Secret | Where to get it |
|---|---|
| `NETLIFY_AUTH_TOKEN` | Netlify → User settings → Applications → Personal access tokens |
| `NETLIFY_SITE_ID` | Netlify → Site settings → General → Site ID |

Add them at: **GitHub repo → Settings → Secrets and variables → Actions**

Or via the CLI:

```bash
gh secret set NETLIFY_AUTH_TOKEN --body "your-token"
gh secret set NETLIFY_SITE_ID --body "your-site-id"
```
