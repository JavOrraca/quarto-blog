#!/usr/bin/env python3
"""Fail CI if draft posts are missing rendered Draft-banner HTML or appear in listings.

GitHub Actions `quarto render`s the site; `website.draft-mode: unlinked` in
`_quarto.yml` still writes full HTML for `draft: true` posts, including the
Draft banner from `format-html.ts`:

  <meta name="quarto:status" content="draft">
  <div id="quarto-draft-alert" class="alert alert-warning">
    <i class="bi bi-pencil-square"></i>Draft
  </div>

`_site/` is gitignored. After render, each draft must have that banner HTML
on disk and must not appear as a Blog listing card. Netlify is published from
CI on main, not from git-tracked HTML.

Usage:
  python3 scripts/check-draft-posts.py
  python3 scripts/check-draft-posts.py --root /path/to/repo
  python3 scripts/check-draft-posts.py --self-test
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


DRAFT_TRUE_RE = re.compile(
    r"^draft:\s*(?:true|yes)\s*(?:#.*)?$",
    re.IGNORECASE | re.MULTILINE,
)
FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
STATUS_META_RE = re.compile(
    r"<meta\b[^>]*\bname\s*=\s*['\"]quarto:status['\"][^>]*\bcontent\s*=\s*['\"]draft['\"]"
    r"|<meta\b[^>]*\bcontent\s*=\s*['\"]draft['\"][^>]*\bname\s*=\s*['\"]quarto:status['\"]",
    re.IGNORECASE,
)
BANNER_RE = re.compile(
    r"<div\b([^>]*\bid\s*=\s*['\"]quarto-draft-alert['\"][^>]*)>(.*?)</div>",
    re.IGNORECASE | re.DOTALL,
)
LISTING_TITLE_HREF_RE = re.compile(
    r'<h3 class="no-anchor listing-title">\s*<a href="([^"]+)"',
    re.IGNORECASE,
)
DRAFT_MODE_RE = re.compile(r"^  draft-mode:\s*(\S+)\s*(?:#.*)?$", re.MULTILINE)

# Quarto 1.10.18 banner: Bootstrap warning alert, pencil icon, text "Draft".
BANNER_ID = "quarto-draft-alert"
BANNER_CLASSES = ("alert", "alert-warning")
BANNER_TEXT = "Draft"


def read_front_matter(text: str) -> str | None:
    match = FRONT_MATTER_RE.search(text)
    return match.group(1) if match else None


def is_draft_qmd(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    front = read_front_matter(text)
    if front is None:
        return False
    return bool(DRAFT_TRUE_RE.search(front))


def discover_drafts(root: Path) -> list[Path]:
    posts = root / "posts"
    if not posts.is_dir():
        return []
    drafts = [p for p in sorted(posts.glob("**/index.qmd")) if is_draft_qmd(p)]
    return drafts


def site_html_for(qmd: Path, root: Path) -> Path:
    rel = qmd.relative_to(root)
    return root / "_site" / rel.with_suffix(".html")


def listing_slug_from_html(html_path: Path, root: Path) -> str:
    return html_path.relative_to(root / "_site").as_posix()


def banner_ok(html: str) -> tuple[bool, str]:
    if not STATUS_META_RE.search(html):
        return False, "missing <meta name=\"quarto:status\" content=\"draft\">"
    match = BANNER_RE.search(html)
    if not match:
        return False, f'missing <div id="{BANNER_ID}"> Draft banner'
    attrs = match.group(1).lower()
    body = re.sub(r"<[^>]+>", "", match.group(2))
    class_attr = re.search(r"class\s*=\s*['\"]([^'\"]+)['\"]", attrs, re.IGNORECASE)
    classes = class_attr.group(1).split() if class_attr else []
    missing = [c for c in BANNER_CLASSES if c not in classes]
    if missing:
        return False, f"banner classes {missing} missing (need {' '.join(BANNER_CLASSES)})"
    if BANNER_TEXT not in body:
        return False, f'banner text {BANNER_TEXT!r} missing'
    return True, "ok"


def listing_card_hrefs(blog_html: str) -> list[str]:
    hrefs = []
    for raw in LISTING_TITLE_HREF_RE.findall(blog_html):
        href = raw.split("?", 1)[0].split("#", 1)[0]
        href = href.lstrip("./")
        if href.startswith("/"):
            href = href[1:]
        hrefs.append(href)
    return hrefs


def check_draft_mode(root: Path) -> list[str]:
    yml = root / "_quarto.yml"
    if not yml.is_file():
        return ["_quarto.yml is missing"]
    text = yml.read_text(encoding="utf-8")
    match = DRAFT_MODE_RE.search(text)
    if match is None:
        return ["_quarto.yml has no website.draft-mode; expected unlinked"]
    mode = match.group(1).strip().strip("'\"")
    if mode != "unlinked":
        return [f"_quarto.yml website.draft-mode is {mode!r}; expected 'unlinked'"]
    return []


def check_repo(root: Path) -> list[str]:
    errors = check_draft_mode(root)
    drafts = discover_drafts(root)
    blog_path = root / "_site" / "blog.html"
    listing_hrefs: list[str] = []
    if blog_path.is_file():
        listing_hrefs = listing_card_hrefs(
            blog_path.read_text(encoding="utf-8", errors="replace")
        )
    else:
        errors.append("_site/blog.html is missing after quarto render")

    if not drafts:
        return errors

    for qmd in drafts:
        html_path = site_html_for(qmd, root)
        rel = html_path.relative_to(root).as_posix()
        slug = listing_slug_from_html(html_path, root)
        qmd_rel = qmd.relative_to(root).as_posix()

        if not html_path.is_file():
            errors.append(
                f"{qmd_rel}: rendered HTML missing at {rel}. "
                "With draft-mode: unlinked, quarto render must emit a full page "
                "with the Draft banner (CI publishes `_site`; do not commit it)."
            )
            continue

        rendered = html_path.read_text(encoding="utf-8", errors="replace")
        ok, reason = banner_ok(rendered)
        if not ok:
            errors.append(
                f"{qmd_rel}: {rel} is not a full unlinked draft page ({reason}). "
                "Empty HTML means draft-mode: gone, not unlinked."
            )

        if slug in listing_hrefs:
            errors.append(
                f"{qmd_rel}: appears as a listing card in _site/blog.html "
                f"({slug}). Unlinked drafts must not be listed."
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repo root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run fixture tests (rendered Draft banner, unlinked listing)",
    )
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()

    root = (args.root or Path(__file__).resolve().parents[1]).resolve()
    drafts = discover_drafts(root)
    if drafts:
        print(f"check-draft-posts: checked {len(drafts)} draft index.qmd file(s)")
    else:
        print("check-draft-posts: no posts/**/index.qmd with draft: true")
    errors = check_repo(root)
    if errors:
        print("check-draft-posts: FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("check-draft-posts: ok")
    return 0


SAMPLE_BANNER = (
    '<meta name="quarto:status" content="draft">\n'
    '<div id="quarto-draft-alert" class="alert alert-warning">'
    '<i class="bi bi-pencil-square"></i>Draft</div>\n'
    "<article>full draft body</article>\n"
)
SAMPLE_LISTING_CARD = """
<div class="list quarto-listing-default">
<div class="quarto-post image-right" data-index="0">
<h3 class="no-anchor listing-title">
<a href="./posts/2026-09-15-example-draft/index.html" class="no-external">Example</a>
</h3>
</div>
</div>
"""


class DraftCheckTests(unittest.TestCase):
    def _repo(self, files: dict[str, str], commit: bool = True) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="check-draft-posts-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        subprocess.run(
            ["git", "config", "user.email", "ci@example.com"], cwd=tmp, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "CI"], cwd=tmp, check=True
        )
        for rel, contents in files.items():
            path = tmp / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")
        if commit and files:
            subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "test"], cwd=tmp, check=True
            )
        return tmp

    def test_unlinked_draft_passes(self) -> None:
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: unlinked\n",
                "posts/2026-09-15-example-draft/index.qmd": (
                    "---\ntitle: Example\ndraft: true\n---\n\nHello\n"
                ),
                "_site/posts/2026-09-15-example-draft/index.html": SAMPLE_BANNER,
                "_site/blog.html": (
                    '<div class="list quarto-listing-default"></div>\n'
                ),
            }
        )
        self.assertEqual(check_repo(root), [])

    def test_rendered_html_need_not_be_git_tracked(self) -> None:
        # Source is committed; render produced HTML on disk; _site is gitignored.
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: unlinked\n",
                "posts/2026-09-15-example-draft/index.qmd": (
                    "---\ntitle: Example\ndraft: true\n---\n\nHello\n"
                ),
                "_site/blog.html": (
                    '<div class="list quarto-listing-default"></div>\n'
                ),
            }
        )
        rendered = root / "_site/posts/2026-09-15-example-draft/index.html"
        rendered.parent.mkdir(parents=True, exist_ok=True)
        rendered.write_text(SAMPLE_BANNER, encoding="utf-8")
        self.assertEqual(check_repo(root), [])

    def test_missing_rendered_html_fails(self) -> None:
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: unlinked\n",
                "posts/2026-09-15-example-draft/index.qmd": (
                    "---\ntitle: Example\ndraft: true\n---\n\nHello\n"
                ),
                "_site/blog.html": (
                    '<div class="list quarto-listing-default"></div>\n'
                ),
            }
        )
        errors = check_repo(root)
        self.assertTrue(any("rendered HTML missing" in e for e in errors), errors)

    def test_empty_html_without_banner_fails(self) -> None:
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: unlinked\n",
                "posts/2026-09-15-example-draft/index.qmd": (
                    "---\ntitle: Example\ndraft: true\n---\n\nHello\n"
                ),
                "_site/posts/2026-09-15-example-draft/index.html": (
                    "<html><body></body></html>\n"
                ),
                "_site/blog.html": (
                    '<div class="list quarto-listing-default"></div>\n'
                ),
            }
        )
        errors = check_repo(root)
        self.assertTrue(any("not a full unlinked draft page" in e for e in errors), errors)

    def test_listing_card_fails(self) -> None:
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: unlinked\n",
                "posts/2026-09-15-example-draft/index.qmd": (
                    "---\ntitle: Example\ndraft: true\n---\n\nHello\n"
                ),
                "_site/posts/2026-09-15-example-draft/index.html": SAMPLE_BANNER,
                "_site/blog.html": SAMPLE_LISTING_CARD,
            }
        )
        errors = check_repo(root)
        self.assertTrue(any("listing card" in e for e in errors), errors)

    def test_published_post_ignored(self) -> None:
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: unlinked\n",
                "posts/2026-09-15-published/index.qmd": (
                    "---\ntitle: Live\ndraft: false\n---\n\nHello\n"
                ),
                "_site/blog.html": (
                    '<div class="list quarto-listing-default"></div>\n'
                ),
            }
        )
        self.assertEqual(check_repo(root), [])

    def test_draft_mode_gone_fails(self) -> None:
        root = self._repo(
            {
                "_quarto.yml": "website:\n  draft-mode: gone\n",
                "_site/blog.html": (
                    '<div class="list quarto-listing-default"></div>\n'
                ),
            }
        )
        errors = check_repo(root)
        self.assertTrue(any("draft-mode is 'gone'" in e for e in errors), errors)


def run_self_test() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DraftCheckTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
