"""
Runs the Apify Google Maps scraper for a given city + service type,
then returns only businesses that have no website listed.
"""

import time
import requests
from config import APIFY_API_KEY, APIFY_ACTOR_ID, MAX_PLACES_PER_SEARCH

APIFY_BASE = "https://api.apify.com/v2"
HEADERS     = {"Authorization": f"Bearer {APIFY_API_KEY}"}


def _start_run(search_string: str, location: str) -> str:
    payload = {
        "searchStringsArray": [f"{search_string} in {location}"],
        "maxCrawledPlacesPerSearch": MAX_PLACES_PER_SEARCH,
        "language": "en",
        "outputAsJson": True,
        "scrapeReviews": True,
        "maxReviews": 10,
        "scrapeImages": True,
        "maxImages": 10,
    }
    resp = requests.post(
        f"{APIFY_BASE}/acts/{APIFY_ACTOR_ID}/runs",
        json=payload,
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]["id"]


def _wait_for_run(run_id: str, poll_interval: int = 10, timeout: int = 600) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        status = resp.json()["data"]["status"]
        if status == "SUCCEEDED":
            return
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Apify run {run_id} did not finish within {timeout}s")


def _fetch_results(run_id: str) -> list[dict]:
    resp = requests.get(
        f"{APIFY_BASE}/actor-runs/{run_id}/dataset/items",
        params={"format": "json"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _no_website(place: dict) -> bool:
    w = place.get("website") or ""
    return not w.strip() or w.strip() == "-"


def scrape_no_website_businesses(service_type: str, location: str) -> list[dict]:
    """
    Scrapes Google Maps for `service_type in location`, returns only
    businesses with no website. Each dict has at minimum:
      title, phone, address, city, country, category, rating,
      reviewsCount, description, hours, imageUrls, googleMapsUrl
    """
    print(f"  → Starting Apify run: {service_type} in {location}")
    run_id = _start_run(service_type, location)
    _wait_for_run(run_id)
    results = _fetch_results(run_id)

    no_site = [r for r in results if _no_website(r)]
    print(f"     {len(no_site)}/{len(results)} have no website")
    return no_site


def scrape_all(service_types: list[str], cities: list[str]) -> list[dict]:
    """
    Iterates all (service_type, city) combos and deduplicates by phone number.
    """
    seen_phones: set[str] = set()
    all_businesses: list[dict] = []

    for city in cities:
        for stype in service_types:
            try:
                results = scrape_no_website_businesses(stype, city)
                for biz in results:
                    phone = (biz.get("phone") or "").strip()
                    if phone and phone not in seen_phones:
                        seen_phones.add(phone)
                        biz["_service_type"] = stype
                        biz["_searched_city"] = city
                        all_businesses.append(biz)
            except Exception as e:
                print(f"  ERROR scraping {stype} in {city}: {e}")
            time.sleep(2)  # polite gap between runs

    return all_businesses
