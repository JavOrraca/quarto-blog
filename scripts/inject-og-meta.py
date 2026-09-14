#!/usr/bin/env python3
"""Post-render: add og:url, og:type, rel=canonical, and fallback og:image.

Idempotent. Registered from _quarto.yml as project.post-render.
Canonical URLs follow Netlify pretty URLs as served on the live site:
  _site/index.html            -> https://www.javierorracadeatcu.com/
  _site/about.html            -> https://www.javierorracadeatcu.com/about
  _site/posts/foo/index.html  -> https://www.javierorracadeatcu.com/posts/foo/
  _site/posts/foo/foo.html    -> https://www.javierorracadeatcu.com/posts/foo/foo
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "_site"
SKIP_DIR_NAMES = {"site_libs"}
HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
SITE_URL_RE = re.compile(r"^(\s*)site-url:\s*(.+)$", re.MULTILINE)


def read_yaml_scalar(raw: str) -> str:
    value = raw.strip().strip("'").strip('"')
    return value.split("#", 1)[0].strip().strip("'").strip('"')


def load_site_config() -> tuple[str, str]:
    yml = (ROOT / "_quarto.yml").read_text(encoding="utf-8")
    site_url = "https://www.javierorracadeatcu.com"
    m = SITE_URL_RE.search(yml)
    if m:
        site_url = read_yaml_scalar(m.group(2)).rstrip("/")

    default_image = "images/og-default.jpg"
    # Prefer website.image (Quarto site-wide fallback), then open-graph.image.
    in_website = False
    in_open_graph = False
    website_image = None
    og_image = None
    for line in yml.splitlines():
        if re.match(r"^website:\s*$", line):
            in_website = True
            in_open_graph = False
            continue
        if in_website and re.match(r"^[^\s]", line):
            in_website = False
            in_open_graph = False
        if in_website and re.match(r"^  open-graph:", line):
            in_open_graph = True
            continue
        if in_website and in_open_graph and re.match(r"^  \S", line) and not line.startswith("    "):
            in_open_graph = False
        if in_website and in_open_graph:
            mm = re.match(r"^\s+image:\s*(.+)$", line)
            if mm:
                og_image = read_yaml_scalar(mm.group(1))
        elif in_website:
            mm = re.match(r"^  image:\s*(.+)$", line)
            if mm:
                website_image = read_yaml_scalar(mm.group(1))
    if website_image:
        default_image = website_image
    elif og_image:
        default_image = og_image
    return site_url, default_image


def pretty_canonical(rel_posix: str, site_url: str) -> str:
    rel = rel_posix.lstrip("/")
    if rel == "index.html":
        return site_url + "/"
    if rel.endswith("/index.html"):
        return f"{site_url}/{rel[: -len('index.html')]}"
    if rel.endswith(".html"):
        return f"{site_url}/{rel[:-5]}"
    return f"{site_url}/{rel}"


def og_type_for(rel_posix: str) -> str:
    rel = rel_posix.lstrip("/")
    if rel.startswith("posts/"):
        return "article"
    return "website"


def has_meta_property(html: str, prop: str) -> bool:
    return re.search(
        rf"<meta\b[^>]*\bproperty\s*=\s*['\"]{re.escape(prop)}['\"]",
        html,
        flags=re.IGNORECASE,
    ) is not None


def has_canonical(html: str) -> bool:
    return re.search(
        r"<link\b[^>]*\brel\s*=\s*['\"]canonical['\"]",
        html,
        flags=re.IGNORECASE,
    ) is not None


def absolute_image_url(site_url: str, image_path: str) -> str:
    if image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    return f"{site_url}/{image_path.lstrip('./')}"


def inject(html: str, tags: list[str]) -> str:
    if not tags:
        return html
    block = "\n".join(tags) + "\n"
    if HEAD_CLOSE_RE.search(html):
        return HEAD_CLOSE_RE.sub(block + "</head>", html, count=1)
    return html


def process_html(path: Path, output_dir: Path, site_url: str, default_image: str) -> list[str]:
    rel = path.relative_to(output_dir).as_posix()
    html = path.read_text(encoding="utf-8", errors="replace")
    canonical = pretty_canonical(rel, site_url)
    og_type = og_type_for(rel)
    added: list[str] = []
    tags: list[str] = []

    if not has_meta_property(html, "og:url"):
        tags.append(f'<meta property="og:url" content="{canonical}">')
        added.append("og:url")
    if not has_meta_property(html, "og:type"):
        tags.append(f'<meta property="og:type" content="{og_type}">')
        added.append("og:type")
    if not has_canonical(html):
        tags.append(f'<link rel="canonical" href="{canonical}">')
        added.append("canonical")
    if not has_meta_property(html, "og:image"):
        image_url = absolute_image_url(site_url, default_image)
        tags.append(f'<meta property="og:image" content="{image_url}">')
        tags.append('<meta property="og:image:width" content="1200">')
        tags.append('<meta property="og:image:height" content="630">')
        added.append("og:image")

    if not tags:
        return added
    path.write_text(inject(html, tags), encoding="utf-8")
    return added


def iter_html_files(output_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in output_dir.rglob("*.html"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def main() -> int:
    output_dir = Path(os.environ.get("QUARTO_PROJECT_OUTPUT_DIR") or DEFAULT_OUTPUT)
    if not output_dir.is_absolute():
        output_dir = (ROOT / output_dir).resolve()
    if not output_dir.is_dir():
        print(f"inject-og-meta: output dir not found: {output_dir}", file=sys.stderr)
        return 1

    site_url, default_image = load_site_config()
    n_files = 0
    n_changed = 0
    for html_path in iter_html_files(output_dir):
        n_files += 1
        added = process_html(html_path, output_dir, site_url, default_image)
        if added:
            n_changed += 1
    print(f"inject-og-meta: scanned {n_files} HTML files, updated {n_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
