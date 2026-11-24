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
from pathlib import Path

API_BASE = os.environ.get("MYSHUB_API_BASE", "https://emltechstudio-myshub-api.hf.space").rstrip("/")
SITE_BASE = os.environ.get("MYSHUB_SITE_BASE", "https://myshub.site").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("MYSHUB_BUSINESSES_DIR", Path(__file__).parent.parent / "businesses"))
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


def is_indexable_shop(item: dict) -> bool:
    """Apply a defensive moderation/visibility filter to public API records."""
    blocked_boolean_fields = (
        "flagged", "is_flagged", "suspended", "is_suspended", "disabled",
        "is_disabled", "hidden", "is_hidden", "private", "is_private",
    )
    if any(item.get(field) is True for field in blocked_boolean_fields):
        return False
    if item.get("is_public") is False or item.get("public") is False:
        return False
    blocked_statuses = {"flagged", "suspended", "disabled", "hidden", "private", "blocked", "removed"}
    status = str(item.get("status") or item.get("visibility") or "").strip().lower()
    return status not in blocked_statuses


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
        if not is_indexable_shop(item):
            continue
        slug = item.get("slug")
        if not slug:
            continue
        unique[safe_slug(slug)] = item
    complete: list[dict] = []
    for slug, summary in unique.items():
        try:
            detail = fetch_json(f"/discover/{urllib.parse.quote(slug)}")
            if not is_indexable_shop(detail):
                continue
            complete.append({**summary, **detail})
        except Exception as exc:
            print(f"Warning: using discovery search fallback for {slug}: {exc}", file=sys.stderr)
            complete.append(summary)
    return complete


def page_html(shop: dict) -> str:
    slug = safe_slug(shop["slug"])
    name = clean_text(shop.get("business_name") or slug, 120)
    tagline = clean_text(shop.get("tagline"), 160)
    description = clean_text(shop.get("description") or tagline or f"Discover {name} on MyShub.", 160)
    location = clean_text(", ".join(
        x for x in (shop.get("city"), shop.get("state"), shop.get("country")) if x
    ), 120)
    category = clean_text(shop.get("category"), 80)
    socials = shop.get("socials") if isinstance(shop.get("socials"), dict) else {}
    public_links = [(clean_text(label, 40), str(url).strip()) for label, url in socials.items() if str(url or "").strip()]
    if shop.get("catalog_url"):
        public_links.append(("Catalog", str(shop["catalog_url"]).strip()))
    # Public human URL. GitHub Pages serves 404.html for this path, and the
    # existing 404.html is the MyShub storefront SPA for /<slug>.
    live_url = f"{SITE_BASE}/{urllib.parse.quote(slug)}"
    public_url = f"{SITE_BASE}/businesses/{urllib.parse.quote(slug)}.html"
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
    if public_links:
        json_ld["sameAs"] = [url for _, url in public_links[:20]]
    link_html = "".join(f'<li><a href="{esc(url)}" rel="noopener noreferrer">{esc(label)}</a></li>' for label, url in public_links[:20])
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
  <style>body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:760px;margin:0 auto;padding:48px 22px;color:#172033;line-height:1.6}}img{{width:96px;height:96px;object-fit:cover;border-radius:22px}}h1{{line-height:1.15}}h2{{margin-top:28px;font-size:1.1rem}}ul{{padding-left:20px}}.muted{{color:#667085}}a{{color:#175cd3;font-weight:700}}</style>
  <script>window.setTimeout(function(){{window.location.replace({json.dumps(live_url)});}},80);</script>
</head>
<body>
  <main>
    <img src=\"{esc(logo_url)}\" alt=\"{esc(name)} logo\" onerror=\"this.src='{esc(SITE_BASE)}/icon.svg'\">
    <h1>{esc(name)}</h1>
    {f'<p><strong>{esc(tagline)}</strong></p>' if tagline else ''}
    <p>{esc(body_desc)}</p>
    {f'<p class=\"muted\">{esc(context)}</p>' if context else ''}
    {f'<h2>Find {esc(name)} online</h2><ul>{link_html}</ul>' if link_html else ''}
    <p><a href=\"{esc(live_url)}\">Open the live MyShub storefront</a></p>
    <noscript><p class=\"muted\">JavaScript is disabled. Use the link above to open the live storefront.</p></noscript>
  </main>
</body>
</html>
"""


def sitemap_xml(shops: list[dict]) -> str:
    urls = [(f"{SITE_BASE}/businesses/", "daily", "0.9")]
    urls.extend((f"{SITE_BASE}/businesses/{urllib.parse.quote(safe_slug(s['slug']))}.html", "daily", "0.7") for s in shops)
    body = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>", '<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">']
    for loc, freq, priority in urls:
        body.append(f"  <url><loc>{html.escape(loc)}</loc><changefreq>{freq}</changefreq><priority>{priority}</priority></url>")
    body.append("</urlset>")
    return "\n".join(body) + "\n"


def directory_index_html(shops: list[dict]) -> str:
    links = []
    for shop in sorted(shops, key=lambda item: clean_text(item.get("business_name") or item.get("slug"), 120).lower()):
        slug = safe_slug(shop["slug"])
        name = clean_text(shop.get("business_name") or slug, 120)
        category = clean_text(shop.get("category"), 80)
        location = clean_text(shop.get("location_label"), 120)
        detail = " · ".join(x for x in (category, location) if x)
        links.append(f'<li><a href="{esc(slug)}.html">{esc(name)}</a>{f" <span>{esc(detail)}</span>" if detail else ""}</li>')
    return f"""<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Businesses on MyShub</title>
  <meta name="description" content="Browse public businesses, shops, services, and brands listed on MyShub.">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{esc(SITE_BASE)}/businesses/">
  <style>body{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;max-width:900px;margin:0 auto;padding:36px 22px;color:#172033;line-height:1.6}}h1{{line-height:1.15}}ul{{padding:0;list-style:none}}li{{padding:12px 0;border-bottom:1px solid #e5e7eb}}a{{color:#175cd3;font-weight:700}}span{{color:#667085;font-size:.9rem}}</style>
</head><body><main>
  <h1>Businesses on MyShub</h1>
  <p>Discover public businesses, shops, services, and brands listed on MyShub.</p>
  <ul>{''.join(links)}</ul>
</main></body></html>\n"""


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
    for shop in shops:
        slug = safe_slug(shop["slug"])
        (OUTPUT_DIR / f"{slug}.html").write_text(page_html(shop), encoding="utf-8")
    (OUTPUT_DIR / "index.html").write_text(directory_index_html(shops), encoding="utf-8")
    (OUTPUT_DIR / "sitemap.xml").write_text(sitemap_xml(shops), encoding="utf-8")
    (OUTPUT_DIR / "manifest.json").write_text(json.dumps({"count": len(shops), "slugs": [s["slug"] for s in shops]}, indent=2) + "\n", encoding="utf-8")
    print(f"Generated {len(shops)} static MyShub business pages in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SEO generation failed: {exc}", file=sys.stderr)
        raise
