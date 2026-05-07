"""
Deploys all generated HTML files to a single Netlify site in one batch.

Strategy:
  - One Netlify site is created on first run; its ID is persisted in netlify_state.json
  - Every pipeline run re-deploys ALL files in generated_sites/ so old pages stay live
  - Each business page lives at {base_url}/{slug}  (Netlify pretty-URLs strip .html)

Netlify free tier: unlimited sites, 100 GB bandwidth/month, 300 build minutes/month.
"""

import io
import json
import time
import zipfile
import requests
from pathlib import Path

NETLIFY_BASE = "https://api.netlify.com/api/v1"
STATE_FILE   = Path("netlify_state.json")


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _get_or_create_site(token: str) -> tuple[str, str]:
    """Returns (site_id, site_url). Creates the site on first call."""
    state = _load_state()
    if "site_id" in state:
        return state["site_id"], state["site_url"]

    resp = requests.post(
        f"{NETLIFY_BASE}/sites",
        json={},
        headers={**_auth(token), "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    site_id  = data["id"]
    site_url = (data.get("ssl_url") or data.get("url", "")).rstrip("/")

    state.update({"site_id": site_id, "site_url": site_url})
    _save_state(state)
    print(f"  Created Netlify site: {site_url}")
    return site_id, site_url


def _wait_for_deploy(deploy_id: str, token: str, timeout: int = 180) -> str:
    """Polls until the deploy is ready. Returns the live site URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{NETLIFY_BASE}/deploys/{deploy_id}",
            headers=_auth(token),
            timeout=15,
        )
        resp.raise_for_status()
        data  = resp.json()
        state = data.get("state", "")
        if state == "ready":
            return (data.get("ssl_url") or data.get("deploy_ssl_url") or "").rstrip("/")
        if state == "error":
            raise RuntimeError(f"Netlify deploy failed: {data.get('error_message', 'unknown error')}")
        time.sleep(4)
    raise TimeoutError("Netlify deploy did not finish within 180 s")


def deploy(output_dir: Path, token: str) -> str:
    """
    Zips every .html file in output_dir and deploys to Netlify.
    Returns the base site URL (e.g. https://amazing-archimedes-abc123.netlify.app).
    Individual business pages are at  {base_url}/{slug}  (pretty-URL, no .html).
    """
    html_files = sorted(output_dir.glob("*.html"))
    if not html_files:
        raise ValueError(f"No HTML files found in {output_dir}")

    site_id, _ = _get_or_create_site(token)

    # Pack all HTML files flat at the ZIP root
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in html_files:
            zf.write(f, f.name)
    buf.seek(0)

    print(f"  Uploading {len(html_files)} pages to Netlify...")
    resp = requests.post(
        f"{NETLIFY_BASE}/sites/{site_id}/deploys",
        data=buf.getvalue(),
        headers={**_auth(token), "Content-Type": "application/zip"},
        timeout=120,
    )
    resp.raise_for_status()
    deploy_data = resp.json()
    deploy_id   = deploy_data["id"]

    print(f"  Deploy queued ({deploy_id}), waiting for ready...")
    live_url = _wait_for_deploy(deploy_id, token)

    # Persist the confirmed live URL
    state = _load_state()
    state["site_url"] = live_url
    _save_state(state)

    print(f"  ✓ Netlify live: {live_url}")
    return live_url


def page_url(base_url: str, slug: str) -> str:
    """Builds the public URL for a specific business page."""
    return f"{base_url.rstrip('/')}/{slug}"
