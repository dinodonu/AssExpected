---
name: download-substack
description: Download Substack articles to markdown with images, specifically for Tic Toc Trading
---

# Download Substack Articles

Download paywalled Substack articles to local markdown files with images. Output goes to the `../tictoc/` folder.

## Quick Reference

```bash
# From saved HTML (preferred for paywalled articles):
uv run download_article.py --html page.html --outdir tictoc

# From URL with cookie:
uv run download_article.py --url <url> --cookie <substack.sid> --outdir tictoc

# From URL (public articles only):
uv run download_article.py --url <url> --outdir tictoc
```

## Step-by-Step: Downloading a Tic Toc Trading Article

Tic Toc Trading (https://tictoctrading.substack.com/) is a paid Substack. Articles are paywalled, so direct URL fetch won't get full content. Use one of these two methods:

### Method 1: Save HTML from Chrome (Recommended)

1. Open the article in Chrome while logged into Substack
2. Use Chrome browser automation to save the page HTML:
   - Execute JavaScript: `document.documentElement.outerHTML` to get full HTML
   - Save to a `.html` file (e.g., via blob download or write to disk)
3. Run the downloader:
   ```bash
   uv run download_article.py --html saved_page.html --outdir tictoc
   ```

### Method 2: Use Substack Cookie

1. Open Chrome DevTools (F12) > Application > Cookies > substack.com
2. Copy the value of `substack.sid` (it's HttpOnly, won't appear in `document.cookie`)
3. Run:
   ```bash
   uv run download_article.py --url https://tictoctrading.substack.com/p/article-slug --cookie <value> --outdir tictoc
   ```
   Or set the environment variable:
   ```bash
   export SUBSTACK_SID=<value>
   uv run download_article.py --url https://tictoctrading.substack.com/p/article-slug --outdir tictoc
   ```

## Output Structure

Each article is saved to its own subfolder under `tictoc/`:

```
tictoc/
  2025-12-28 silver-is-headed-higher/
    article.md        # Full article in markdown
    images/
      img_00_xxxx.png # Downloaded chart/image files
      img_01_xxxx.png
  2026-02-22 bitcoin-to-0-tariffs-to-stay/
    article.md
    images/
      ...
```

Folder names are prefixed with the article's publication date in `YYYY-MM-DD` format, so they sort chronologically.

### Markdown Format

The generated `article.md` contains:

- **YAML frontmatter**: title, subtitle, author, date, source URL
- **Formatted body**: headings, paragraphs, bold/italic, links, blockquotes, lists
- **Local image references**: images are downloaded and referenced as `images/img_XX_hash.ext`
- **Disclaimer stripped**: the standard Tic Toc disclaimer boilerplate is automatically removed

## What Gets Extracted

| Element | Handling |
|---------|----------|
| Text paragraphs | Converted to markdown with inline formatting |
| Headings (h1-h6) | Converted to `#` syntax |
| Bold / Italic | `**bold**` / `*italic*` |
| Links | `[text](url)` |
| Blockquotes | `> quoted text` |
| Ordered / unordered lists | `1.` / `-` syntax |
| Images & charts | Downloaded to `images/`, referenced locally |
| Figure captions | Rendered as `*caption*` below image |
| Code blocks | Backtick syntax |

## What Gets Skipped

- Subscribe/paywall widgets
- Poll embeds
- Share dialogs
- Button wrappers
- Avatar images
- Footer/post-footer sections

## Bulk Download via Archive

To download multiple articles from the Tic Toc archive:

1. Navigate to https://tictoctrading.substack.com/archive in Chrome (while logged in)
2. Collect article URLs by scrolling through the archive page
3. For each article, save the HTML and run the downloader:
   ```bash
   for html_file in saved_pages/*.html; do
     uv run download_article.py --html "$html_file" --outdir tictoc
   done
   ```

## Dependencies

Managed via `uv`. The project's `pyproject.toml` includes:
- `beautifulsoup4` — HTML parsing
- `requests` — HTTP requests and image downloads
