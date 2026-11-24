#!/usr/bin/env python3
"""Generate crawler/social-preview pages for public MyShub shops.

The generated pages are intentionally separate from the application root. They
contain public metadata and a small content-bearing preview, then send normal
visitors into the existing SPA storefront.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = os.environ.get("MYSHUB_API_BASE", "https://emltechstudio-myshub-api.hf.space").rstrip("/")
SITE_BASE = os.environ.get("MYSHUB_SITE_BASE", "https://myshub.site").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("MYSHUB_SEO_DIR", Path(__file__).parent / "generated"))
PAGE_SIZE = 100


def fetch_json(path: str) -> dict:
    request = urllib.request.Request(
        API_BASE + path,
        headers={"Accept": "application/json", "User-Agent": "MyShub-SEO-Generator/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def clean_text(value: object, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].rstrip()


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def safe_slug(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", value):
        raise ValueError(f"Unsafe or unsupported shop slug: {value!r}")
    return value


def get_all_shops() -> list[dict]:
    first = fetch_json(f"/discover/search?limit={PAGE_SIZE}&page=1")
    total = int(first.get("total") or len(first.get("results") or []))
    results = list(first.get("results") or [])
    page = 2
    while len(results) < total:
        data = fetch_json(f"/discover/search?limit={PAGE_SIZE}&page={page}")
        batch = data.get("results") or []
        if not batch:
            break
        results.extend(batch)
        page += 1
    unique: dict[str, dict] = {}
    for item in results:
        slug = item.get("slug")
        if not slug:
            continue
        unique[safe_slug(slug)] = item
    return list(unique.values())


def page_html(shop: dict, generated_at: str) -> str:
    slug = safe_slug(shop["slug"])
    name = clean_text(shop.get("business_name") or slug, 120)
    tagline = clean_text(shop.get("tagline"), 160)
    description = clean_text(shop.get("description") or tagline or f"Discover {name} on MyShub.", 160)
    location = clean_text(shop.get("location_label") or ", ".join(
        x for x in (shop.get("city"), shop.get("state"), shop.get("country")) if x
    ), 120)
    category = clean_text(shop.get("category"), 80)
    # Public human URL. GitHub Pages serves 404.html for this path, and the
    # existing 404.html is the MyShub storefront SPA for /<slug>.
    live_url = f"{SITE_BASE}/{urllib.parse.quote(slug)}"
    public_url = f"{SITE_BASE}/seo-pages/{urllib.parse.quote(slug)}/"
    logo_url = f"{API_BASE}/discover/logo/{urllib.parse.quote(slug)}" if shop.get("has_logo") else f"{SITE_BASE}/icon.svg"
    page_title = f"{name} | MyShub"
    bits = [x for x in (category, location) if x]
    context = " · ".join(bits)
    body_desc = description + (f" ({context})" if context else "")
    json_ld = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
        "description": description,
        "url": live_url,
        "image": logo_url,
        "provider": {"@type": "Organization", "name": "MyShub", "url": SITE_BASE},
    }
    if location:
        json_ld["address"] = {"@type": "PostalAddress", "addressLocality": location}
    if category:
        json_ld["additionalType"] = category
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <title>{esc(page_title)}</title>
  <meta name=\"description\" content=\"{esc(description)}\">
  <meta name=\"robots\" content=\"index,follow,max-image-preview:large\">
  <link rel=\"canonical\" href=\"{esc(live_url)}\">
  <meta property=\"og:type\" content=\"website\">
  <meta property=\"og:url\" content=\"{esc(live_url)}\">
  <meta property=\"og:title\" content=\"{esc(page_title)}\">
  <meta property=\"og:description\" content=\"{esc(description)}\">
  <meta property=\"og:image\" content=\"{esc(logo_url)}\">
  <meta property=\"og:site_name\" content=\"MyShub\">
  <meta name=\"twitter:card\" content=\"summary_large_image\">
  <meta name=\"twitter:title\" content=\"{esc(page_title)}\">
  <meta name=\"twitter:description\" content=\"{esc(description)}\">
  <meta name=\"twitter:image\" content=\"{esc(logo_url)}\">
  <script type=\"application/ld+json\">{json.dumps(json_ld, ensure_ascii=False, separators=(",", ":"))}</script>
  <style>body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:760px;margin:0 auto;padding:48px 22px;color:#172033;line-height:1.6}}img{{width:96px;height:96px;object-fit:cover;border-radius:22px}}h1{{line-height:1.15}}.muted{{color:#667085}}a{{color:#175cd3;font-weight:700}}</style>
  <script>window.setTimeout(function(){{window.location.replace({json.dumps(live_url)});}},80);</script>
</head>
<body>
  <main>
    <img src=\"{esc(logo_url)}\" alt=\"{esc(name)} logo\" onerror=\"this.src='{esc(SITE_BASE)}/icon.svg'\">
    <h1>{esc(name)}</h1>
    {f'<p><strong>{esc(tagline)}</strong></p>' if tagline else ''}
    <p>{esc(body_desc)}</p>
    {f'<p class=\"muted\">{esc(context)}</p>' if context else ''}
    <p><a href=\"{esc(live_url)}\">Open the live MyShub storefront</a></p>
    <noscript><p class=\"muted\">JavaScript is disabled. Use the link above to open the live storefront.</p></noscript>
  </main>
  <!-- Generated {esc(generated_at)} from public MyShub discovery data. -->
</body>
</html>
"""


def sitemap_xml(shops: list[dict], generated_at: str) -> str:
    urls = [
        (f"{SITE_BASE}/", "daily", "1.0"),
        (f"{SITE_BASE}/discover.html", "daily", "0.9"),
    ]
    # Canonicals point at the public /<slug> storefront URL, not this generator directory.
    urls.extend((f"{SITE_BASE}/{urllib.parse.quote(safe_slug(s['slug']))}", "daily", "0.7") for s in shops)
    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", '<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">']
    for loc, freq, priority in urls:
        body.append(f"  <url><loc>{html.escape(loc)}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>")
    body.append("</urlset>")
    return "\n".join(body) + "\n"


def merge_root_sitemap(shops: list[dict]) -> None:
    root_path = Path(__file__).parent.parent / "sitemap.xml"
    text = root_path.read_text(encoding="utf-8") if root_path.exists() else '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n'
    existing = set(re.findall(r"<loc>([^<]+)</loc>", text))
    additions: list[str] = []
    for shop in shops:
        slug = safe_slug(shop["slug"])
        loc_value = f"{SITE_BASE}/{urllib.parse.quote(slug)}"
        if loc_value in existing:
            continue
        additions.append(f"    <url>\n        <loc>{html.escape(loc_value)}</loc>\n        <changefreq>daily</changefreq>\n        <priority>0.7</priority>\n    </url>\n")
    if additions:
        closing = "</urlset>"
        if closing not in text:
            raise RuntimeError("Root sitemap is missing </urlset>")
        text = text.replace(closing, "".join(additions) + closing, 1)
        root_path.write_text(text, encoding="utf-8")


def main() -> int:
    shops = get_all_shops()
    if not shops:
        raise RuntimeError("Discovery API returned no public shops; refusing to delete generated pages")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for child in OUTPUT_DIR.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for shop in shops:
        slug = safe_slug(shop["slug"])
        target = OUTPUT_DIR / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / "index.html").write_text(page_html(shop, generated_at), encoding="utf-8")
    (Path(__file__).parent / "sitemap-shops.xml").write_text(sitemap_xml(shops, generated_at), encoding="utf-8")
    merge_root_sitemap(shops)
    (Path(__file__).parent / "manifest.json").write_text(json.dumps({"generated_at": generated_at, "count": len(shops), "slugs": [s["slug"] for s in shops]}, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(shops)} static MyShub SEO pages in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SEO generation failed: {exc}", file=sys.stderr)
        raise
