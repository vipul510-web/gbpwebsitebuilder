"""
Uses GPT-4o-mini to generate website copy from GBP data,
then renders it into the HTML template.
"""

import re
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client  = OpenAI(api_key=OPENAI_API_KEY)
env     = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _generate_copy(biz: dict) -> dict:
    name        = biz.get("title", "")
    category    = biz.get("categoryName") or biz.get("_service_type", "")
    description = biz.get("description") or ""
    city        = biz.get("city") or biz.get("_searched_city", "")

    prompt = f"""You are writing website copy for a local home-services business.

Business details:
- Name: {name}
- Category: {category}
- City: {city}
- Description from Google: {description or "not provided"}

Return ONLY a JSON object with these exact keys:
{{
  "tagline": "one punchy sentence, max 10 words",
  "about": "2-3 sentences about the business, warm and professional",
  "services": ["service 1", "service 2", "service 3", "service 4", "service 5"],
  "cta": "one action phrase for the contact button, max 5 words",
  "faqs": [
    {{"q": "question 1", "a": "answer 1"}},
    {{"q": "question 2", "a": "answer 2"}},
    {{"q": "question 3", "a": "answer 3"}},
    {{"q": "question 4", "a": "answer 4"}},
    {{"q": "question 5", "a": "answer 5"}}
  ]
}}

For faqs: write the 5 most common questions a potential customer would search for when hiring a {category} in {city}. Answers should be 1-2 sentences, practical and trust-building."""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=700,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def _format_hours(hours_data) -> list[str]:
    if not hours_data:
        return []
    if isinstance(hours_data, list):
        out = []
        for h in hours_data:
            if isinstance(h, dict):
                day   = h.get("day") or h.get("name") or ""
                times = h.get("hours") or h.get("time") or h.get("value") or ""
                out.append(f"{day}: {times}" if day else str(h))
            else:
                out.append(str(h))
        return out
    if isinstance(hours_data, dict):
        return [f"{k}: {v}" for k, v in hours_data.items()]
    return [str(hours_data)]


def _extract_reviews(biz: dict, max_reviews: int = 5) -> list[dict]:
    """Returns up to max_reviews review dicts with name, stars, text, date."""
    raw = biz.get("reviews") or []
    out = []
    for r in raw:
        text = (r.get("text") or r.get("textTranslated") or "").strip()
        if not text:
            continue
        stars = r.get("stars") or r.get("rating") or 5
        name  = (r.get("name") or r.get("reviewerName") or "Customer").strip()
        date  = (r.get("publishAt") or r.get("date") or "").strip()
        # Trim date to just the date part if it's an ISO string
        if "T" in date:
            date = date.split("T")[0]
        # Truncate very long reviews
        if len(text) > 300:
            text = text[:297] + "..."
        out.append({"name": name, "stars": int(stars), "text": text, "date": date})
        if len(out) >= max_reviews:
            break
    return out


def _extract_coords(biz: dict) -> tuple[float | None, float | None]:
    loc = biz.get("location") or {}
    lat = biz.get("latitude")  or loc.get("lat")
    lng = biz.get("longitude") or loc.get("lng")
    if lat is None or lng is None:
        return None, None
    try:
        return float(lat), float(lng)
    except (TypeError, ValueError):
        return None, None


def generate_site(biz: dict, output_dir: Path) -> Path:
    """
    Generates a complete HTML file for the business.
    Returns the path to the generated file.
    """
    name     = biz.get("title", "Business")
    phone    = biz.get("phone", "")
    address  = biz.get("address") or biz.get("street", "")
    city     = biz.get("city") or biz.get("_searched_city", "")
    country  = "GB" if "UK" in (biz.get("_searched_city") or "").upper() else "US"
    rating   = biz.get("totalScore") or biz.get("rating")
    rev_count= biz.get("reviewsCount", 0)
    images   = biz.get("imageUrls") or biz.get("images") or []
    hours    = _format_hours(biz.get("openingHours") or biz.get("hours"))
    maps_url = biz.get("url") or biz.get("googleMapsUrl", "#")
    reviews  = _extract_reviews(biz)
    lat, lng = _extract_coords(biz)
    category = biz.get("categoryName") or biz.get("_service_type", "")

    copy = _generate_copy(biz)

    template_vars = {
        "business_name": name,
        "tagline":       copy["tagline"],
        "about":         copy["about"],
        "services":      copy["services"],
        "cta":           copy["cta"],
        "faqs":          copy.get("faqs", []),
        "phone":         phone,
        "address":       address,
        "city":          city,
        "country":       country,
        "category":      category,
        "rating":        rating,
        "reviews_count": rev_count,
        "hours":         hours,
        "gallery":       images[:8],
        "hero_image":    images[0] if images else "",
        "maps_url":      maps_url,
        "reviews":       reviews,
        "lat":           lat,
        "lng":           lng,
    }

    template = env.get_template("business.html")
    html     = template.render(**template_vars)

    slug      = _slug(name)
    out_path  = output_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
