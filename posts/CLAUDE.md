# posts/CLAUDE.md: Writing Style Guide

Authoritative guide for all post creation on Data Science Bytes.
Read this entirely before writing or editing any post.

---

## YAML Front Matter Template

```yaml
---
title: "Catchy, descriptive title"
description: "1-2 sentence summary that tells readers exactly what they will learn."
date: MM-DD-YYYY
categories: [tag1, tag2, tag3]
image: preview.jpg
draft: true
---
```

Rules:
- `draft: true` on every new post -the user removes it before publishing
- Date format: `MM-DD-YYYY` (e.g., `03-14-2026`)
- Categories: lowercase, hyphens for multi-word tags
- `image` must match an actual file in the post folder

**Fields inherited from `_metadata.yml` -do NOT include in post front matter:**
`author`, `freeze`, `license`, `toc`, `toc-title`, `toc-location`, `execute`

---

## Known Categories (reuse when applicable)

```
r, python, tidyverse, tidymodels, shiny, quarto, arrow, duckdb, polars,
langchain, huggingface, chromadb, positron, r6, databricks, brickster,
httr2, mlflow, sparklyr
```

Add new categories only when a topic is genuinely new to the site.

---

## Post Folder and File Structure

```
posts/YYYY-MM-DD-kebab-case-title/
├── index.qmd          ← always this filename
└── preview.jpg        ← placed here, not in an images/ subdirectory
```

---

## Javier's Voice: 5 Defining Qualities

1. **Professional but conversational** -explain to a smart colleague over
   coffee, not presenting to a review board.

2. **Opinionated and credible** -share a clear point of view backed by
   experience. "I recommend X because..." not "Some people prefer X."

3. **Self-aware and occasionally funny** -light humor, parenthetical
   asides, footnotes for digressions. Never try-hard.

4. **Mentor-like** -anticipate what a reader one step behind needs.
   Explain the "why", not just the "what."

5. **Community-generous** -credit tools, authors, and resources by name.
   Link generously. Invite feedback at the close.

Personal pronouns: use "I've", "In my experience", "I recommend" freely.
Closings: warm, often "happy [day], and happy coding!"

---

## Post Structure Pattern

1. YAML front matter
2. Image placeholder comment (see below) + `![](preview.jpg){.preview-image}`
3. H1 hook -reword the title into a statement or question; must differ from YAML title
4. Opening paragraph -personal framing, why this matters to the audience
5. 2–4 substantive sections (H1 or H2 headers)
6. Practical angle: code example, workflow tip, or concrete recommendation
7. Credits / "Learn More" block linking source and related resources
8. Warm closing paragraph
9. `# sessionInfo()` block (technical R posts only, with `#| eval: false`)

Short paragraphs: 3–4 lines max. Lists for multi-item points.

---

## Quarto Formatting Reference

**Preview image** (first content line after front matter):
```
![](preview.jpg){.preview-image}
```

**External links** (always open in new tab):
```
[Link text](https://example.com){target="_blank"}
```

**Two-column layout** (logo + text):
```
::: columns
::: {.column width="65%"}
Text here...
:::
::: {.column width="35%"}
![](logo.png)
:::
:::
```

**Callout tip**:
```
::: {.callout-tip}
## Tip Title
Content here.
:::
```

**Illustrative code block** (not executed):
````
```{r}
#| eval: false
# code here
```
````

**Footnote / aside** for digressions:
```
^[Footnote text here.]
```

---

## Image Placeholder

Claude cannot download web images. Insert this comment before the preview
image line whenever creating a new post:

```
<!-- TODO: Add preview image -save a relevant image as `preview.jpg`
     (or rename as needed), update `image:` in the YAML above, and
     update the filename in the ![]() line below. -->
```

---

## Quality Checklist

Before finishing any draft, verify:

- [ ] YAML has `draft: true`
- [ ] Date is `MM-DD-YYYY` format
- [ ] Inherited fields (`author`, `freeze`, etc.) not duplicated in YAML
- [ ] Image placeholder comment present; `![](preview.jpg){.preview-image}` on line after
- [ ] H1 hook header differs from YAML title
- [ ] Opening paragraph is personal and explains why this matters
- [ ] All external links have `{target="_blank"}`
- [ ] Illustrative code blocks have `#| eval: false`
- [ ] No paragraph exceeds ~4 lines
- [ ] Source URL credited with a link
- [ ] Closing is warm (ends with "happy coding!" or similar)
- [ ] Categories are lowercase, from known list where possible
- [ ] No files created or modified outside `posts/YYYY-MM-DD-slug/`
