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
  "cta": "one action phrase for the contact button, max 5 words"
}}"""

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=400,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def _format_hours(hours_data) -> list[str]:
    if not hours_data:
        return []
    if isinstance(hours_data, list):
        return [str(h) for h in hours_data]
    if isinstance(hours_data, dict):
        return [f"{k}: {v}" for k, v in hours_data.items()]
    return [str(hours_data)]


def generate_site(biz: dict, output_dir: Path) -> Path:
    """
    Generates a complete HTML file for the business.
    Returns the path to the generated file.
    """
    name     = biz.get("title", "Business")
    phone    = biz.get("phone", "")
    address  = biz.get("address") or biz.get("street", "")
    city     = biz.get("city") or biz.get("_searched_city", "")
    rating   = biz.get("totalScore") or biz.get("rating")
    reviews  = biz.get("reviewsCount", 0)
    images   = biz.get("imageUrls") or biz.get("images") or []
    hours    = _format_hours(biz.get("openingHours") or biz.get("hours"))
    maps_url = biz.get("url") or biz.get("googleMapsUrl", "#")

    copy = _generate_copy(biz)

    template_vars = {
        "business_name": name,
        "tagline":       copy["tagline"],
        "about":         copy["about"],
        "services":      copy["services"],
        "cta":           copy["cta"],
        "phone":         phone,
        "address":       address,
        "city":          city,
        "rating":        rating,
        "reviews":       reviews,
        "hours":         hours,
        "hero_image":    images[0] if images else "",
        "maps_url":      maps_url,
    }

    template = env.get_template("business.html")
    html     = template.render(**template_vars)

    slug      = _slug(name)
    out_path  = output_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
