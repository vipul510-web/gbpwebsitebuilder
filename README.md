# GBP Website Builder

An automated pipeline that finds local home-service businesses with no website on Google Maps, generates a professional website for each one using GPT-4o-mini, deploys them all to Netlify, and sends a WhatsApp outreach message to every business owner — fully hands-off.

```
Apify (Google Maps)  →  GPT-4o-mini  →  Netlify  →  WhatsApp (Gavi)
```

---

## How it works

| Phase | What happens |
|-------|-------------|
| **1 — Scrape** | Runs the [Apify Google Maps scraper](https://apify.com/compass/crawler-google-places) across every (service type × city) combination you configure. Filters to businesses with no website listed. Deduplicates by phone number. |
| **2 — Generate** | For each business, calls GPT-4o-mini to write a tagline, about section, services list, and CTA. Renders it into a responsive Jinja2 HTML template using real GBP data (phone, address, rating, reviews, photos, hours, Google Maps link). |
| **3 — Deploy** | ZIPs all generated HTML files and deploys them to a single Netlify site in one batch. The Netlify site ID is persisted in `netlify_state.json` so subsequent runs update the same site. Each business gets a clean pretty-URL: `{site_url}/{business-slug}`. |
| **4 — Outreach** | Sends a pre-approved WhatsApp template message to each business via Gavi Ventures, with their name and newly generated site URL embedded. |

---

## Prerequisites

- Python 3.11+
- Accounts and API keys for:
  - [Apify](https://console.apify.com/account/integrations) — uses the free `compass~crawler-google-places` actor
  - [OpenAI](https://platform.openai.com/api-keys) — GPT-4o-mini
  - [Netlify](https://app.netlify.com/user/applications) — personal access token (free tier is sufficient)
  - [Gavi Ventures](https://gaviventures.com) — WhatsApp messaging API

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/vipul510-web/gbpwebsitebuilder.git
cd gbpwebsitebuilder
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys:

```env
APIFY_API_KEY=apify_xxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
GAVI_API_KEY=gv_xxxxxxxxxxxxxxxxxxxx
GAVI_TEMPLATE_NAME=website_offer
NETLIFY_ACCESS_TOKEN=nfp_xxxxxxxxxxxxxxxxxxxx
```

### 4. Set up your WhatsApp template (one-time)

Before the pipeline can send messages, you need a WhatsApp-approved template in Gavi:

1. Log into [gaviventures.com](https://gaviventures.com) → **Templates → Create New**
2. Use this template body:
   ```
   Hi {{1}}, we noticed your business doesn't have a website yet.
   We built one for you for free — take a look: {{2}}
   No strings attached. Reply YES to claim it.
   ```
3. Submit for WhatsApp approval (typically 1–24 hours)
4. Set `GAVI_TEMPLATE_NAME` in your `.env` to the approved template name

---

## Usage

### Dry run (recommended first step)

Runs Phases 1 and 2 for real (Apify scrape + GPT site generation), but **skips** the Netlify deploy and WhatsApp sends. Safe and cheap — caps at 5 businesses.

```bash
python pipeline.py --dry-run --limit 5
```

Output:
- `generated_sites/` — the generated HTML files you can preview locally
- `results.json` — a log of what would have been deployed/sent
- Console shows mock URLs and the WhatsApp messages that *would* be sent

### Live run (single market)

```bash
python pipeline.py --market US
```

### Full run (US + UK)

```bash
python pipeline.py
```

### Re-deploy without re-scraping

If you've already generated sites and just want to redeploy (e.g. after editing templates):

```bash
python pipeline.py --skip-scrape
```

---

## CLI flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Skip Netlify deploy and WhatsApp sends; print mock output |
| `--limit N` | Cap the number of businesses processed (useful for testing) |
| `--market US\|UK` | Restrict to one or both markets (default: both) |
| `--skip-scrape` | Skip Apify scrape; redeploy all existing HTML files in `generated_sites/` |

---

## Project structure

```
gbp-website-pipeline/
├── pipeline.py          # Main orchestrator — runs all 4 phases
├── apify_scraper.py     # Apify Google Maps scraper + no-website filter
├── site_generator.py    # GPT-4o-mini copy generation + Jinja2 HTML render
├── deployer.py          # Netlify ZIP deploy + site state persistence
├── whatsapp.py          # Gavi Ventures WhatsApp template sender
├── config.py            # Cities, service types, env var loading
├── templates/
│   └── business.html    # Responsive single-page website template
├── requirements.txt
├── .env.example
├── generated_sites/     # Created at runtime — one .html per business
├── netlify_state.json   # Created at runtime — Netlify site ID + URL
└── results.json         # Created at runtime — full run log
```

---

## Configuration

Edit `config.py` to change which cities and service types are scraped:

```python
HOME_SERVICE_TYPES = [
    "plumber",
    "electrician",
    "hvac contractor",
    "roofing contractor",
    "general contractor",
    "painter",
    "locksmith",
    "pest control service",
    "house cleaning service",
    "landscaper",
]

US_CITIES = [
    "New York NY USA",
    "Los Angeles CA USA",
    ...
]

UK_CITIES = [
    "London UK",
    "Manchester UK",
    ...
]
```

Also configurable:

```python
MAX_PLACES_PER_SEARCH = 40   # Apify results per (service × city) run
                              # Drop to 20 to stay within Apify free tier (~$5/mo)
```

---

## Cost estimate (default config)

| Service | Usage | Estimated cost |
|---------|-------|---------------|
| Apify | 10 types × 10 cities × 40 places = 4,000 records @ ~$0.003/place | ~$12/run |
| OpenAI (GPT-4o-mini) | ~400 tokens per business, ~4,000 businesses | ~$1–2/run |
| Netlify | Free tier — unlimited sites, 100 GB bandwidth/month | $0 |
| Gavi WhatsApp | Per message — check your plan | varies |

**To stay within the Apify free tier (~$5/mo):** set `MAX_PLACES_PER_SEARCH = 20` in `config.py`, which yields ~2,000 records per run.

---

## Generated website

Each business gets a responsive single-page site with:

- **Hero** — business name, GPT-generated tagline, click-to-call button, Google Maps link, and the business's own Google photo as the background
- **Trust badges** — Licensed & Insured, Same-Day Service, Local Experts, Free Estimates
- **About** — GPT-generated copy + Google rating/review count card
- **Services** — 5 AI-generated service items based on the business category
- **Contact** — phone, address, opening hours, Google Maps embed button
- **Sticky nav** — business name + CTA call button always visible

The template is pure HTML/CSS (no JS frameworks, no external dependencies beyond Google Fonts) so pages load instantly and are easily customisable.

---

## Outputs

After each run you'll find:

| File/folder | Contents |
|-------------|----------|
| `generated_sites/*.html` | One HTML file per business, named by slug (e.g. `joes-plumbing-chicago.html`) |
| `netlify_state.json` | Netlify site ID and live URL — reused on subsequent runs |
| `results.json` | Full log: business name, phone, city, category, site URL, WhatsApp sent status |

---

## Troubleshooting

**Apify run times out**
Increase the `timeout` parameter in `apify_scraper._wait_for_run` (default 600 s). Large cities with many results take longer.

**Netlify deploy fails on re-run**
Delete `netlify_state.json` to force creation of a new site, or check that your token hasn't expired.

**WhatsApp messages rejected**
The template must be approved by WhatsApp before use. Ensure `GAVI_TEMPLATE_NAME` in `.env` exactly matches the approved template name in your Gavi dashboard.

**Phone numbers skipped**
The pipeline uses the `phonenumbers` library to normalise numbers to E.164. Numbers that can't be parsed are skipped with a warning. UK businesses are parsed with a `GB` country hint; all others default to `US`.
