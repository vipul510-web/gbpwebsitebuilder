"""
Sends WhatsApp template messages via the Gavi Ventures API.

IMPORTANT: These are cold contacts (businesses we've never messaged before),
so we MUST use a pre-approved template — plain text messages will be rejected
by WhatsApp for new conversations.

Setup steps before running:
  1. Log into gaviventures.com → Templates → Create New
  2. Use this template body:
       Hi {{1}}, we noticed your business doesn't have a website yet.
       We built one for you for free — take a look: {{2}}
       No strings attached. Reply YES to claim it.
  3. Submit for WhatsApp approval (usually 1-24 hours)
  4. Set GAVI_TEMPLATE_NAME in your .env once approved
"""

import re
import requests
import phonenumbers
from config import GAVI_API_KEY, GAVI_BASE_URL, GAVI_TEMPLATE_NAME

HEADERS = {
    "Authorization": f"Bearer {GAVI_API_KEY}",
    "Content-Type": "application/json",
}


def normalize_phone(raw: str, country_hint: str = "US") -> str | None:
    """
    Converts any phone format to E.164 (e.g. +14155552671).
    Returns None if the number can't be parsed.
    """
    try:
        # Strip non-digit chars except leading +
        cleaned = re.sub(r"[^\d+]", "", raw.strip())
        parsed  = phonenumbers.parse(cleaned, country_hint)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None


def send_template(to: str, business_name: str, site_url: str) -> dict:
    """
    Sends the website_offer template to `to` (E.164 format).
    Variables: {{1}} = business_name, {{2}} = site_url
    """
    payload = {
        "to":       to,
        "template": GAVI_TEMPLATE_NAME,
        "language": "en",
        "variables": {
            "1": business_name,
            "2": site_url,
        },
    }
    resp = requests.post(
        f"{GAVI_BASE_URL}/api/v1/messages/template",
        json=payload,
        headers=HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def send_to_business(biz: dict, site_url: str) -> bool:
    """
    Normalizes the phone number and sends the WhatsApp message.
    Returns True on success, False on any failure.
    """
    raw_phone   = (biz.get("phone") or "").strip()
    country     = "GB" if "UK" in (biz.get("_searched_city") or "").upper() else "US"
    name        = biz.get("title", "there")

    e164 = normalize_phone(raw_phone, country)
    if not e164:
        print(f"  SKIP {name}: could not parse phone '{raw_phone}'")
        return False

    try:
        result = send_template(e164, name, site_url)
        print(f"  ✓ WhatsApp sent to {name} ({e164}) — message id: {result.get('id', '?')}")
        return True
    except requests.HTTPError as e:
        print(f"  ✗ WhatsApp failed for {name} ({e164}): {e.response.text}")
        return False
