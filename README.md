# caladapt-guidance-test

Testing site for AE guidance website migration to a new framework using Quarto, with support for search and a blog :)

## Local development

Install [Quarto](https://quarto.org/docs/get-started/), then run:

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
