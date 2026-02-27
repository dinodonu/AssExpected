#!/usr/bin/env python3
"""
Download a Substack article to Markdown with images.

Usage:
    # From saved HTML (best for paid/paywalled articles):
    uv run download_article.py --html page.html [--outdir articles]

    # From URL with cookie:
    uv run download_article.py --url <url> --cookie <substack.sid> [--outdir articles]

    # From URL (public articles only):
    uv run download_article.py --url <url> [--outdir articles]

To save HTML from Chrome for paywalled articles:
    1. Open the article in Chrome while logged in
    2. Right-click > Save as > Webpage, HTML Only
    3. Run: uv run download_article.py --html saved_page.html

Or copy the cookie:
    1. Open DevTools (F12) > Application > Cookies > substack.com
    2. Copy the value of `substack.sid` (it's HttpOnly, won't show in JS)
    3. Run: uv run download_article.py --url <url> --cookie <value>
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup, NavigableString, Tag


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


def get_image_filename(url: str, index: int) -> str:
    """Derive a short filename from the image URL."""
    decoded = unquote(urlparse(url).path)
    match = re.search(r"images/([a-f0-9\-]+)\.(png|jpg|jpeg|gif|webp)", decoded, re.I)
    if match:
        return f"img_{index:02d}_{match.group(1)[:12]}.{match.group(2)}"
    ext = "jpg"
    for candidate in ["png", "gif", "webp", "jpeg"]:
        if candidate in decoded.lower():
            ext = candidate
            break
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"img_{index:02d}_{url_hash}.{ext}"


def get_best_image_url(img_tag: Tag) -> str | None:
    """Get the highest-quality image URL from an <img>."""
    src = img_tag.get("src", "")
    if "substackcdn.com" in src:
        src = re.sub(r"w_\d+", "w_1456", src, count=1)
    return src or None


def is_skip_element(el_class_str: str) -> bool:
    """Check if element should be skipped (non-content)."""
    skip_classes = [
        "button-wrapper", "subscribe-widget", "paywall-jump",
        "poll-embed", "chat-widget", "share-dialog",
        "footer-wrap", "post-footer", "subscription-widget",
    ]
    return any(skip in el_class_str for skip in skip_classes)


def get_class_str(el: Tag) -> str:
    el_class = el.get("class", [])
    if isinstance(el_class, list):
        return " ".join(el_class)
    return el_class or ""


def inline_to_markdown(el: Tag, img_rel: str, images: list) -> str:
    """Convert inline HTML content (inside a <p>, <li>, etc.) to Markdown."""
    parts = []
    for child in el.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            if child.name in ("strong", "b"):
                inner = inline_to_markdown(child, img_rel, images)
                parts.append(f"**{inner}**")
            elif child.name in ("em", "i"):
                inner = inline_to_markdown(child, img_rel, images)
                parts.append(f"*{inner}*")
            elif child.name == "a":
                href = child.get("href", "")
                text = child.get_text()
                if href and text:
                    parts.append(f"[{text}]({href})")
                else:
                    parts.append(text or "")
            elif child.name == "br":
                parts.append("  \n")
            elif child.name == "code":
                parts.append(f"`{child.get_text()}`")
            elif child.name == "img":
                url = get_best_image_url(child)
                if url and "avatar" not in url:
                    idx = len(images)
                    fname = get_image_filename(url, idx)
                    images.append((url, fname))
                    alt = child.get("alt", "")
                    parts.append(f"![{alt}]({img_rel}/{fname})")
            elif child.name == "span":
                # Recurse into spans (Substack uses them for formatting)
                parts.append(inline_to_markdown(child, img_rel, images))
            else:
                parts.append(child.get_text())
    return "".join(parts)


def convert_element(el, img_rel: str, images: list) -> str:
    """Recursively convert an HTML element to Markdown."""
    if isinstance(el, NavigableString):
        return ""
    if not isinstance(el, Tag):
        return ""

    tag = el.name
    cls = get_class_str(el)

    if is_skip_element(cls):
        return ""

    # Captioned image container
    if "captioned-image-container" in cls:
        img = el.find("img")
        caption_el = el.find("figcaption")
        if img:
            url = get_best_image_url(img)
            if url:
                idx = len(images)
                fname = get_image_filename(url, idx)
                images.append((url, fname))
                alt = img.get("alt", "")
                caption = caption_el.get_text(strip=True) if caption_el else alt
                md = f"\n![{caption}]({img_rel}/{fname})\n"
                if caption and caption != alt:
                    md += f"*{caption}*\n"
                return md
        return ""

    # Figure (standalone)
    if tag == "figure":
        img = el.find("img")
        caption_el = el.find("figcaption")
        if img:
            url = get_best_image_url(img)
            if url:
                idx = len(images)
                fname = get_image_filename(url, idx)
                images.append((url, fname))
                alt = img.get("alt", "")
                caption = caption_el.get_text(strip=True) if caption_el else alt
                md = f"\n![{caption}]({img_rel}/{fname})\n"
                if caption and caption != alt:
                    md += f"*{caption}*\n"
                return md
        return ""

    # Standalone image
    if tag == "img":
        url = get_best_image_url(el)
        if url and "avatar" not in url and str(el.get("width", "")) != "36":
            idx = len(images)
            fname = get_image_filename(url, idx)
            images.append((url, fname))
            alt = el.get("alt", "")
            return f"\n![{alt}]({img_rel}/{fname})\n"
        return ""

    # Headings
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1])
        text = el.get_text(strip=True)
        return f"\n{'#' * level} {text}\n"

    # Paragraph
    if tag == "p":
        inner = inline_to_markdown(el, img_rel, images)
        if not inner.strip():
            return ""
        return f"\n{inner}\n"

    # Blockquote
    if tag == "blockquote":
        inner = ""
        for child in el.children:
            inner += convert_element(child, img_rel, images)
        lines = inner.strip().split("\n")
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"\n{quoted}\n"

    # Lists
    if tag in ("ul", "ol"):
        items = []
        for i, li in enumerate(el.find_all("li", recursive=False)):
            prefix = f"{i + 1}." if tag == "ol" else "-"
            text = inline_to_markdown(li, img_rel, images).strip()
            items.append(f"{prefix} {text}")
        return "\n" + "\n".join(items) + "\n"

    # Horizontal rule
    if tag == "hr":
        return "\n---\n"

    # Div or other container — recurse into children
    if tag in ("div", "span", "section", "article", "main", "picture", "source",
               "table", "thead", "tbody", "tr"):
        parts = []
        for child in el.children:
            parts.append(convert_element(child, img_rel, images))
        return "".join(parts)

    # Table cells
    if tag in ("td", "th"):
        return f" {el.get_text(strip=True)} |"

    # Links as block-level (rare)
    if tag == "a":
        href = el.get("href", "")
        text = el.get_text(strip=True)
        if text and href:
            return f"[{text}]({href})"
        return text or ""

    # Bold / Italic at block level
    if tag in ("strong", "b"):
        return f"**{inline_to_markdown(el, img_rel, images)}**"
    if tag in ("em", "i"):
        return f"*{inline_to_markdown(el, img_rel, images)}*"

    # Fallback
    return el.get_text()


def parse_article(soup: BeautifulSoup, source_url: str, outdir: str) -> str:
    """Parse a Substack article soup and save as Markdown with images."""
    # Extract metadata
    title_el = soup.select_one("h1.post-title")
    title = title_el.get_text(strip=True) if title_el else "Untitled"

    subtitle_el = soup.select_one("h3.subtitle")
    subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""

    author_meta = soup.find("meta", attrs={"name": "author"})
    author = author_meta["content"] if author_meta and author_meta.get("content") else "Unknown"

    # Extract date from byline
    date = ""
    for el in soup.select("article .pencraft"):
        t = el.get_text()
        m = re.search(r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})", t)
        if m:
            date = m.group(1)
            break
    # Fallback: try subtitle (e.g. "Weekly Plan 12.28.25")
    if not date and subtitle:
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})", subtitle)
        if m:
            date = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"

    # Get post body
    body = soup.select_one(".body.markup")
    if not body:
        print("ERROR: Could not find article body (.body.markup).")
        print("       Is the article paywalled? Try --html with a saved page.")
        sys.exit(1)

    # Determine output directory
    if source_url:
        slug = urlparse(source_url).path.rstrip("/").split("/")[-1]
    else:
        slug = slugify(title)

    # Parse date into ISO format for folder prefix
    iso_date = ""
    if date:
        for fmt in ("%b %d, %Y", "%m/%d/%y", "%m/%d/%Y"):
            try:
                iso_date = datetime.strptime(date, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

    folder_name = f"{iso_date} {slug}" if iso_date else slug
    article_dir = Path(outdir) / folder_name
    img_dir = article_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_rel = "images"

    # Convert body to markdown
    images = []
    md_parts = []
    for child in body.children:
        md_parts.append(convert_element(child, img_rel, images))

    body_md = "\n".join(md_parts)
    body_md = re.sub(r"\n{3,}", "\n\n", body_md).strip()

    # Build full markdown
    full_md = f"""---
title: "{title}"
subtitle: "{subtitle}"
author: "{author}"
date: "{date}"
source: "{source_url}"
---

# {title}

*{subtitle}*
*{author} — {date}*

{body_md}"""

    # Strip disclaimer boilerplate
    disclaimer_marker = "Disclaimer: This newsletter is not intended to provide trading"
    idx = full_md.find(disclaimer_marker)
    if idx > 0:
        full_md = full_md[:idx].rstrip()

    # Write markdown
    md_path = article_dir / "article.md"
    md_path.write_text(full_md, encoding="utf-8")
    print(f"Saved markdown: {md_path}")

    # Download images
    if images:
        print(f"Downloading {len(images)} images...")
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }
        for img_url, fname in images:
            img_path = img_dir / fname
            if img_path.exists():
                print(f"  Skip (exists): {fname}")
                continue
            try:
                resp = requests.get(img_url, headers=headers, timeout=30)
                resp.raise_for_status()
                img_path.write_bytes(resp.content)
                print(f"  Downloaded: {fname} ({len(resp.content) // 1024}KB)")
            except Exception as e:
                print(f"  FAILED: {fname} — {e}")
    else:
        try:
            img_dir.rmdir()
        except OSError:
            pass

    print(f"\nDone! Article saved to {article_dir}/")
    return str(md_path)


def fetch_url(url: str, cookie: str) -> BeautifulSoup:
    """Fetch article HTML from URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    }
    cookies = {"substack.sid": cookie} if cookie else {}
    print(f"Fetching {url} ...")
    resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def main():
    parser = argparse.ArgumentParser(
        description="Download a Substack article to Markdown with images.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Substack article URL")
    group.add_argument("--html", help="Path to saved HTML file")

    parser.add_argument(
        "--cookie",
        default=os.environ.get("SUBSTACK_SID", ""),
        help="substack.sid cookie value (or set SUBSTACK_SID env var)",
    )
    parser.add_argument(
        "--outdir",
        default="articles",
        help="Output directory (default: articles/)",
    )
    args = parser.parse_args()

    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"ERROR: File not found: {args.html}")
            sys.exit(1)
        print(f"Reading {args.html} ...")
        soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
        # Try to get URL from canonical link
        canonical = soup.find("link", rel="canonical")
        source_url = canonical["href"] if canonical and canonical.get("href") else ""
    else:
        if not args.cookie:
            print("WARNING: No cookie provided. Paywalled articles won't be accessible.")
            print("         Set --cookie or SUBSTACK_SID env var.\n")
        soup = fetch_url(args.url, args.cookie)
        source_url = args.url

    parse_article(soup, source_url, args.outdir)


if __name__ == "__main__":
    main()
