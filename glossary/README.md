# Glossary

`glossary-data.json` is the only file you need to edit to add or update terms. The generate script runs automatically on every `quarto render` or `quarto preview`.

To link to a term from another page (includes a hover tooltip):

```markdown
[model run](/glossary/index.qmd#model-run)
```

The `slug` for each term is defined in `glossary-data.json`.
