# CLAUDE.md: Data Science Bytes (Quarto Blog)

Project: Javier Orraca-Deatcu's personal data science blog.
Site title: "Data Science Bytes"
Site URL: https://www.javierorracadeatcu.com
Stack: Quarto + R -themes Flatly (light) / Darkly (dark)

---

## CRITICAL: What Claude May and May Not Touch

### Allowed
- Create and edit files inside `/posts/`
- Commit `_freeze/` updates when knitr actually re-ran. Do not commit `_site/`
  (gitignored; GitHub Actions publishes to Netlify).

### Prohibited -never modify these
- `_quarto.yml` -site config; editing breaks the build
- `_site/` -compiled output; never hand-edit HTML and do not commit it
- `_freeze/` -cached computation; never edit directly
- `_extensions/` -Quarto extensions
- `index.qmd`, `about.qmd`, `blog.qmd`, `resources.qmd` -top-level pages
- `theme-light.scss`, `theme-dark.scss` -stylesheets
- `.claude/settings.local.json` -permissions config
- `posts/_metadata.yml` -inherited post defaults; read-only reference

---

## Rendering

GitHub Actions (`.github/workflows/quarto-render.yml`) renders the site on
pull requests and on pushes to `main`. Posts inherit `freeze: auto` from
`posts/_metadata.yml` with committed `_freeze/` (Quarto re-knits when source
changes; `freeze: true` never re-knits on a project render). Do not set
`freeze: false` on drafts; freeze only controls knitr, not whether HTML is
emitted. CI restores R 4.6.1 packages from `renv.lock`.

`website.draft-mode: unlinked` in `_quarto.yml` is required. Quarto 1.10
renders `draft: true` posts as full HTML with a Draft banner (`#quarto-draft-alert`)
and keeps them out of nav/listings/search/sitemap. `_site/` is gitignored.
PR CI validates the rendered Draft banner; merge to `main` publishes to
Netlify via `quarto-dev/quarto-actions/publish@v2`.

Local `quarto::quarto_render(as_job = FALSE)` is still how Javier drafts and
refreshes freeze. **Do not run a full `quarto render` unless Javier asks.**

When a post draft is complete, tell the user:
> "Draft created at `posts/YYYY-MM-DD-slug/index.qmd`. Add a preview image,
> review the content, and keep `draft: true` (freeze inherits `auto`). PR CI
> renders and checks the Draft banner; merge to main publishes to Netlify.
> Do not commit `_site/`. Remove `draft: true` when ready to publish."

---

## Post Naming Convention

```
posts/YYYY-MM-DD-kebab-case-title/
└── index.qmd
```

- Folder date format: `YYYY-MM-DD`
- YAML front matter date format: `MM-DD-YYYY`
- Always use today's actual date
- Folder slug: lowercase, hyphens only, 3–6 words, descriptive but concise
- Main file is always `index.qmd` (never named after the folder)
- Images go directly in the post folder (not in an `images/` subdirectory)

---

## Writing Guidelines

All writing style guidance, voice, YAML templates, formatting patterns,
categories taxonomy, and quality checklist live in:

→ **`posts/CLAUDE.md`**

Read that file in full before drafting any post content.

---

## Drafting a Post from a URL

Invoke the `/draft-blog-post` skill:

```
/draft-blog-post <URL>
```

The skill handles: fetching the URL, synthesizing insights in Javier's voice,
creating `posts/YYYY-MM-DD-slug/index.qmd`, and reporting next steps.
