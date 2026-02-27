#!/usr/bin/env python3
"""
Process batch JSON files from Substack API into Markdown articles.

Usage:
    uv run process_batch.py articles_batch1.json [articles_batch2.json ...] --outdir tictoc
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

from download_article import (
    convert_element,
    get_image_filename,
    get_best_image_url,
)
import requests


def process_article(article: dict, outdir: str) -> str | None:
    """Process a single article dict from the Substack API."""
    if "error" in article:
        print(f"  SKIP (error): {article['slug']} — {article['error']}")
        return None

    slug = article["slug"]
    title = article["title"]
    subtitle = article.get("subtitle", "")
    author = article.get("author", "Tic Toc Trading")
    date_str = article.get("date", "")
    canonical_url = article.get("canonical_url", "")
    body_html = article.get("body_html", "")

    if not body_html:
        print(f"  SKIP (no body): {slug}")
        return None

    # Parse date
    iso_date = ""
    display_date = ""
    if date_str:
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            iso_date = dt.strftime("%Y-%m-%d")
            display_date = dt.strftime("%b %d, %Y")
        except (ValueError, TypeError):
            pass

    # Build folder
    folder_name = f"{iso_date} {slug}" if iso_date else slug
    article_dir = Path(outdir) / folder_name

    # Skip if already exists
    md_path = article_dir / "article.md"
    if md_path.exists():
        print(f"  SKIP (exists): {folder_name}")
        return str(md_path)

    img_dir = article_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    img_rel = "images"

    # Parse body_html with BeautifulSoup
    soup = BeautifulSoup(body_html, "html.parser")

    # Convert to markdown using existing converter
    images = []
    md_parts = []
    for child in soup.children:
        md_parts.append(convert_element(child, img_rel, images))

    body_md = "\n".join(md_parts)

    # Clean up excessive newlines
    import re
    body_md = re.sub(r"\n{3,}", "\n\n", body_md).strip()

    # Build full markdown
    full_md = f"""---
title: "{title}"
subtitle: "{subtitle}"
author: "{author}"
date: "{display_date}"
source: "{canonical_url}"
---

# {title}

*{subtitle}*
*{author} — {display_date}*

{body_md}"""

    # Strip disclaimer boilerplate
    disclaimer_marker = "Disclaimer: This newsletter is not intended to provide trading"
    idx = full_md.find(disclaimer_marker)
    if idx > 0:
        full_md = full_md[:idx].rstrip()

    # Write markdown
    md_path.write_text(full_md, encoding="utf-8")

    # Download images
    if images:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        }
        for img_url, fname in images:
            img_path = img_dir / fname
            if img_path.exists():
                continue
            try:
                resp = requests.get(img_url, headers=headers, timeout=30)
                resp.raise_for_status()
                img_path.write_bytes(resp.content)
            except Exception as e:
                print(f"    IMG FAIL: {fname} — {e}")
    else:
        try:
            img_dir.rmdir()
        except OSError:
            pass

    print(f"  OK: {folder_name} ({len(images)} images)")
    return str(md_path)


def main():
    parser = argparse.ArgumentParser(description="Process batch Substack API JSON files.")
    parser.add_argument("files", nargs="+", help="JSON batch files")
    parser.add_argument("--outdir", default="tictoc", help="Output directory")
    args = parser.parse_args()

    total = 0
    saved = 0
    skipped = 0

    for filepath in args.files:
        print(f"\nProcessing {filepath}...")
        with open(filepath) as f:
            articles = json.load(f)

        for article in articles:
            total += 1
            result = process_article(article, args.outdir)
            if result:
                saved += 1
            else:
                skipped += 1

    print(f"\nDone! {saved} saved, {skipped} skipped, {total} total.")


if __name__ == "__main__":
    main()
