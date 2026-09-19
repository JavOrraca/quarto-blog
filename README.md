# Personal Blog using Quarto

Every few years, I like to update my personal data science website using bleeding-edge web frameworks. Several years back, I built my first data science blog using the R Markdown + [blogdown](https://bookdown.org/yihui/blogdown/) framework, then I ported it to the R Markdown + [distill](https://rstudio.github.io/distill/) framework, and this latest iteration of my site is built with Quarto.

I draft locally with `quarto::quarto_render(as_job = FALSE)` so I can preview posts and refresh `_freeze/` when knitr needs to re-run. GitHub Actions renders on pull requests (validate only) and on pushes to `main` (render, then publish). Posts inherit `freeze: auto` from `posts/_metadata.yml` (including drafts; freeze only controls code execution). `_quarto.yml` sets `website.draft-mode: unlinked`, so a `draft: true` post is rendered with Quarto's Draft banner and kept off the Blog listing, search, and sitemap. `_site/` is gitignored; Netlify is published from GitHub Actions, not from committed HTML.

## Deploy

This follows Quarto's recommended GitHub Actions → Netlify path ([Publishing to Netlify](https://quarto.org/docs/publishing/netlify.html), [Publishing with CI](https://quarto.org/docs/publishing/ci.html)):

1. **Local:** edit source, render to preview, and commit `_freeze/` when computations change. Do not commit `_site/`.
2. **Pull requests:** `.github/workflows/quarto-render.yml` installs Quarto 1.10.18 and R 4.6.1, restores packages from `renv.lock`, runs `quarto render` (including `scripts/inject-og-meta.py` as `project.post-render`), then `scripts/check-draft-posts.py` against the rendered `_site`. PRs do **not** publish. A `_site` artifact is uploaded for debugging.
3. **Merge to `main`:** the same render + checks run, then `quarto-dev/quarto-actions/publish@v2` publishes to Netlify with `render: false` so the already-checked `_site` (OG tags included) is what goes live.

Publishing credentials and destination:

- GitHub Actions secret `NETLIFY_AUTH_TOKEN` (Netlify personal access token)
- `_publish.yml` records the Netlify site id and `https://www.javierorracadeatcu.com`

`netlify.toml` skips git-triggered Netlify builds so production is not overwritten from the Git tree (which no longer contains `_site/`). After the first green Actions publish on `main`, stop auto-publishing from Git in the Netlify UI if it is still enabled (Site configuration → Build & deploy → Continuous deployment).

# About Quarto

[Quarto](https://quarto.org/) is "an open-source scientific and publishing system built on Pandoc" that allows you to natively write and render code chunks with Python, R, Julia, Observable, and more. With Quarto, you can publish high-quality articles, reports, presentations, websites, blogs, and books in HTML, PDF, MS Word, ePub, and more.

While [R Markdown](https://rmarkdown.rstudio.com/) is not going anywhere, Quarto represents a more advanced and simpler successor to the R Markdown framework. If you're an R programmer comfortable with R Markdown, you should feel zero change by moving to Quarto. If you're a Python programmer comfortable with rendering Jupyter notebooks to print and HTML formats, you will also feel at home with Quarto. If you're completely new to this type of system, the Quarto homepage has a ton of great resources including a robust [gallery](https://quarto.org/docs/gallery/) from which you can gain ideas and inspiration.
