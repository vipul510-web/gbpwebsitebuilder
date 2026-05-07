"""
Main pipeline: scrape → generate sites → deploy to Netlify → send WhatsApp

Phase 1  Scrape   — Apify Google Maps → filter no-website businesses
Phase 2  Generate — GPT-4o-mini + HTML template → one .html per business
Phase 3  Deploy   — ZIP all HTMLs → one Netlify deployment → get live URLs
Phase 4  Outreach — Gavi WhatsApp template message per business with their URL

Usage:
  cp .env.example .env      # fill in your API keys
  pip install -r requirements.txt
  python pipeline.py --dry-run --limit 5    # safe test
  python pipeline.py --market UK            # UK only, live run
  python pipeline.py                        # full US + UK run

Outputs:
  generated_sites/      one HTML file per business (persists across runs)
  netlify_state.json    Netlify site ID + URL (reused on subsequent runs)
  results.json          full run log
"""

import json
import time
import argparse
from pathlib import Path
from datetime import datetime

from config import US_CITIES, UK_CITIES, HOME_SERVICE_TYPES, NETLIFY_TOKEN
from apify_scraper import scrape_all
from site_generator import generate_site
from deployer import deploy, page_url
from whatsapp import send_to_business

OUTPUT_DIR  = Path("generated_sites")
RESULTS_LOG = Path("results.json")


def run_pipeline(
    dry_run: bool = False,
    limit: int | None = None,
    markets: list[str] | None = None,
    skip_scrape: bool = False,
) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    city_names = []
    if not markets or "US" in markets:
        city_names += US_CITIES
    if not markets or "UK" in markets:
        city_names += UK_CITIES

    print(f"\n{'='*60}")
    print(f"GBP Website Pipeline — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Markets : {', '.join(markets or ['US', 'UK'])}")
    print(f"Cities  : {len(city_names)}")
    print(f"Dry run : {dry_run}")
    print(f"{'='*60}\n")

    # ── Phase 1: Scrape ───────────────────────────────────────────
    if skip_scrape:
        print("PHASE 1 — Skipped (using previously generated sites)\n")
        businesses = []
    else:
        print("PHASE 1 — Scraping no-website businesses via Apify...\n")
        businesses = scrape_all(HOME_SERVICE_TYPES, city_names)
        if limit:
            businesses = businesses[:limit]
        print(f"\nFound {len(businesses)} unique no-website businesses\n")
        if not businesses:
            print("Nothing to process. Try broadening cities or service types.")
            return

    # ── Phase 2: Generate sites ───────────────────────────────────
    print("PHASE 2 — Generating websites with GPT-4o-mini...\n")
    generated: list[tuple[dict, Path]] = []   # (biz, html_path)

    for i, biz in enumerate(businesses, 1):
        name = biz.get("title", "Unknown")
        print(f"  [{i}/{len(businesses)}] {name}")
        try:
            path = generate_site(biz, OUTPUT_DIR)
            generated.append((biz, path))
            print(f"    → {path.name}")
        except Exception as e:
            print(f"    Site generation FAILED: {e}")

    # ── Phase 3: Deploy to Netlify ────────────────────────────────
    all_html_files = list(OUTPUT_DIR.glob("*.html"))
    print(f"\nPHASE 3 — Deploying {len(all_html_files)} pages to Netlify...\n")

    if dry_run:
        base_url = "https://dry-run-preview.netlify.app"
        print(f"  DRY RUN — skipping Netlify deploy, using mock URL: {base_url}\n")
    else:
        try:
            base_url = deploy(OUTPUT_DIR, NETLIFY_TOKEN)
        except Exception as e:
            print(f"  Netlify deploy FAILED: {e}")
            print("  Aborting — fix Netlify config and re-run with --skip-scrape")
            return

    # ── Phase 4: WhatsApp outreach ────────────────────────────────
    print(f"\nPHASE 4 — Sending WhatsApp messages...\n")
    results = []

    for biz, site_path in generated:
        name     = biz.get("title", "Unknown")
        slug     = site_path.stem
        site_url = page_url(base_url, slug)

        wa_sent = False
        if dry_run:
            phone = biz.get("phone", "no phone")
            print(f"  DRY RUN [{name}] → {phone}  |  {site_url}")
        else:
            wa_sent = send_to_business(biz, site_url)
            time.sleep(1)   # avoid hitting rate limits

        results.append({
            "name":      name,
            "phone":     biz.get("phone"),
            "city":      biz.get("city") or biz.get("_searched_city"),
            "category":  biz.get("_service_type"),
            "site_url":  site_url,
            "wa_sent":   wa_sent,
        })

    # ── Save log ──────────────────────────────────────────────────
    RESULTS_LOG.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    sent  = sum(1 for r in results if r["wa_sent"])
    sites = len(generated)

    print(f"\n{'='*60}")
    print(f"Done.")
    print(f"  Businesses processed : {len(results)}")
    print(f"  Websites live        : {sites}  →  {base_url}")
    print(f"  WhatsApp sent        : {sent}")
    print(f"  Results log          : {RESULTS_LOG}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GBP → Website → WhatsApp Pipeline")
    parser.add_argument("--dry-run",     action="store_true", help="Skip Netlify deploy and WhatsApp sends")
    parser.add_argument("--limit",       type=int,            help="Cap number of businesses to process")
    parser.add_argument("--market",      choices=["US","UK"], nargs="+", help="Restrict to one or both markets")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip Apify scrape, just redeploy existing HTML files")
    args = parser.parse_args()

    run_pipeline(
        dry_run     = args.dry_run,
        limit       = args.limit,
        markets     = args.market,
        skip_scrape = args.skip_scrape,
    )
