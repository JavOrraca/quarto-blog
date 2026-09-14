#!/usr/bin/env python3
"""Audit Open Graph, Twitter Card, and canonical tags from a sitemap.

Examples:
  python scripts/og-audit.py --base https://www.javierorracadeatcu.com
  python scripts/og-audit.py --base https://deploy-preview-N--site.netlify.app -o preview.csv
  python scripts/og-audit.py --sitemap _site/sitemap.xml --local-site _site -o local.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "DataScienceBytes-og-audit/1.0 (+https://www.javierorracadeatcu.com)"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
META_KEYS = (
    "og:title",
    "og:description",
    "og:image",
    "og:type",
    "og:url",
    "canonical",
    "twitter:card",
)


class HeadParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self._stop = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._stop:
            return
        ad = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = ad.get("property") or ad.get("name")
            if key:
                self.meta[key.lower()] = ad.get("content", "")
        elif tag == "link" and "canonical" in ad.get("rel", "").lower().split():
            self.meta["canonical"] = ad.get("href", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self._stop = True


def fetch_bytes(url: str, timeout: int = 30) -> tuple[int, dict[str, str], bytes]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return status, headers, resp.read()
    except HTTPError as exc:
        headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
        body = exc.read() if exc.fp else b""
        return exc.code, headers, body


def parse_sitemap(xml_bytes: bytes) -> list[str]:
    root = ET.fromstring(xml_bytes)
    locs = [el.text.strip() for el in root.findall(".//sm:loc", SITEMAP_NS) if el.text]
    if locs:
        return locs
    return [el.text.strip() for el in root.findall(".//{*}loc") if el.text]


def rewrite_sitemap_locs(locs: Iterable[str], base: str) -> list[str]:
    base = base.rstrip("/")
    out: list[str] = []
    for loc in locs:
        parsed = urlparse(loc)
        path = parsed.path or "/"
        out.append(base + path + (("?" + parsed.query) if parsed.query else ""))
    return out


def local_html_path(local_site: Path, url: str) -> Path | None:
    path = urlparse(url).path
    if path.endswith("/"):
        candidate = local_site / path.lstrip("/") / "index.html"
        if candidate.is_file():
            return candidate
    if path.endswith(".html"):
        candidate = local_site / path.lstrip("/")
        if candidate.is_file():
            return candidate
        pretty = local_site / (path.lstrip("/")[:-5] + ".html")
        if pretty.is_file():
            return pretty
    else:
        candidate = local_site / (path.lstrip("/") + ".html")
        if candidate.is_file():
            return candidate
        idx = local_site / path.lstrip("/") / "index.html"
        if idx.is_file():
            return idx
    if path in ("", "/"):
        homepage = local_site / "index.html"
        if homepage.is_file():
            return homepage
    return None


def local_file_for_url(local_site: Path, url: str) -> Path | None:
    parsed = urlparse(url)
    rel = parsed.path.lstrip("/")
    if not rel:
        return None
    candidate = local_site / rel
    if candidate.is_file():
        return candidate
    return None


def parse_head(html: str) -> dict[str, str]:
    parser = HeadParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    return parser.meta


def image_dimensions(data: bytes) -> str:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            return f"{im.width}x{im.height}"
    except Exception:
        return ""


def inspect_image(image_url: str, local_site: Path | None) -> tuple[str, str, str]:
    if not image_url:
        return "", "", ""
    if local_site is not None:
        local = local_file_for_url(local_site, image_url)
        if local and local.is_file():
            data = local.read_bytes()
            return "200", str(len(data)), image_dimensions(data)
    try:
        status, headers, data = fetch_bytes(image_url)
        length = headers.get("content-length") or str(len(data))
        return str(status), length, image_dimensions(data)
    except (URLError, TimeoutError, OSError) as exc:
        return f"error:{exc.__class__.__name__}", "", ""


def row_for_page(url: str, html: str, local_site: Path | None) -> dict[str, str]:
    meta = parse_head(html)
    image = meta.get("og:image", "")
    status, length, wh = inspect_image(image, local_site)
    return {
        "url": url,
        "og:title": meta.get("og:title", ""),
        "og:description": meta.get("og:description", ""),
        "og:image": image,
        "og:type": meta.get("og:type", ""),
        "og:url": meta.get("og:url", ""),
        "canonical": meta.get("canonical", ""),
        "twitter:card": meta.get("twitter:card", ""),
        "image HTTP status": status,
        "content-length": length,
        "WxH": wh,
    }


def summarize(rows: list[dict[str, str]]) -> str:
    n = len(rows)
    def missing(key: str) -> int:
        return sum(1 for r in rows if not r.get(key))

    over_500 = 0
    over_1600 = 0
    for r in rows:
        try:
            if int(r["content-length"] or 0) > 500 * 1024:
                over_500 += 1
        except ValueError:
            pass
        wh = r.get("WxH") or ""
        m = re.match(r"(\d+)x(\d+)", wh)
        if m and int(m.group(1)) > 1600:
            over_1600 += 1
    lines = [
        f"pages: {n}",
        f"missing og:title: {missing('og:title')}/{n}",
        f"missing og:description: {missing('og:description')}/{n}",
        f"missing og:image: {missing('og:image')}/{n}",
        f"missing og:type: {missing('og:type')}/{n}",
        f"missing og:url: {missing('og:url')}/{n}",
        f"missing canonical: {missing('canonical')}/{n}",
        f"missing twitter:card: {missing('twitter:card')}/{n}",
        f"og:image >500KB: {over_500}",
        f"og:image >1600px wide: {over_1600}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        help="Site origin, e.g. https://www.javierorracadeatcu.com or a Netlify deploy preview",
    )
    parser.add_argument("--sitemap", help="Path or URL to sitemap.xml")
    parser.add_argument(
        "--local-site",
        help="Read HTML and images from a local _site directory instead of HTTP",
    )
    parser.add_argument("-o", "--out", default="og-audit.csv", help="CSV output path")
    args = parser.parse_args()

    local_site = Path(args.local_site).resolve() if args.local_site else None
    sitemap_source = args.sitemap
    if not sitemap_source:
        if not args.base and local_site is None:
            parser.error("provide --base and/or --sitemap / --local-site")
        if local_site is not None and (local_site / "sitemap.xml").is_file() and not args.base:
            sitemap_bytes = (local_site / "sitemap.xml").read_bytes()
            locs = parse_sitemap(sitemap_bytes)
        else:
            base = (args.base or "https://www.javierorracadeatcu.com").rstrip("/")
            sitemap_bytes = fetch_bytes(urljoin(base + "/", "sitemap.xml"))[2]
            locs = parse_sitemap(sitemap_bytes)
            locs = rewrite_sitemap_locs(locs, base)
    else:
        sm = Path(sitemap_source)
        if sm.is_file():
            sitemap_bytes = sm.read_bytes()
        else:
            sitemap_bytes = fetch_bytes(sitemap_source)[2]
        locs = parse_sitemap(sitemap_bytes)
        if args.base:
            locs = rewrite_sitemap_locs(locs, args.base.rstrip("/"))

    rows: list[dict[str, str]] = []
    for url in locs:
        if local_site is not None:
            html_path = local_html_path(local_site, url)
            if html_path is None:
                rows.append(
                    {
                        "url": url,
                        "og:title": "",
                        "og:description": "",
                        "og:image": "",
                        "og:type": "",
                        "og:url": "",
                        "canonical": "",
                        "twitter:card": "",
                        "image HTTP status": "missing-local-html",
                        "content-length": "",
                        "WxH": "",
                    }
                )
                continue
            html = html_path.read_text(encoding="utf-8", errors="replace")
        else:
            status, _, body = fetch_bytes(url)
            if status >= 400:
                rows.append(
                    {
                        "url": url,
                        "og:title": "",
                        "og:description": "",
                        "og:image": "",
                        "og:type": "",
                        "og:url": "",
                        "canonical": "",
                        "twitter:card": "",
                        "image HTTP status": str(status),
                        "content-length": "",
                        "WxH": "",
                    }
                )
                continue
            html = body.decode("utf-8", errors="replace")
        rows.append(row_for_page(url, html, local_site))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "url",
                "og:title",
                "og:description",
                "og:image",
                "og:type",
                "og:url",
                "canonical",
                "twitter:card",
                "image HTTP status",
                "content-length",
                "WxH",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(summarize(rows), file=sys.stderr)
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
