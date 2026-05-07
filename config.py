import os
from dotenv import load_dotenv

load_dotenv()

APIFY_API_KEY       = os.environ["APIFY_API_KEY"]
OPENAI_API_KEY      = os.environ["OPENAI_API_KEY"]
GAVI_API_KEY        = os.environ["GAVI_API_KEY"]
GAVI_TEMPLATE_NAME  = os.environ.get("GAVI_TEMPLATE_NAME", "website_offer")

APIFY_ACTOR_ID      = "compass~crawler-google-places"
MAX_PLACES_PER_SEARCH = 40   # keeps total well inside Apify free tier (~$5/mo)

# Home services search terms that map well to Google Maps categories
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

# 5 US + 5 UK cities → 10 types × 10 cities = 100 Apify runs × 40 results = 4,000 records
# Apify charges per place returned (~$0.003), so ~$12 total — adjust MAX_PLACES_PER_SEARCH
# down to 20 to stay within the $5 free tier (~2,000 records).
US_CITIES = [
    "New York NY USA",
    "Los Angeles CA USA",
    "Chicago IL USA",
    "Houston TX USA",
    "Phoenix AZ USA",
]

UK_CITIES = [
    "London UK",
    "Manchester UK",
    "Birmingham UK",
    "Leeds UK",
    "Bristol UK",
]

NETLIFY_TOKEN = os.environ["NETLIFY_ACCESS_TOKEN"]

GAVI_BASE_URL = "https://www.gaviventures.com"
OPENAI_MODEL  = "gpt-4o-mini"
