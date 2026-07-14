# Google Images API

A self-hosted Google Images scraping API. Retrieve real-time image search
results with
high-resolution original URLs, thumbnails, source details, suggestions, and
related searches. Filter by size, color, image type, time period, usage
rights, and aspect ratio.

Built with **FastAPI** + **Playwright**.

## Why a headless browser?

Google requires JavaScript for search (since January 2025) and serves a bot
interstitial to plain HTTP clients. This API drives a real headless Chromium
that passes Google's JS challenge, then parses the embedded JSON result data
out of the page. Pagination uses Google's own async batch endpoint, called
from inside the established browser session.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium      # bundled fallback browser
cp .env.example .env             # optional: set API_KEYS etc.
uvicorn app.main:app --port 8000
```

If Google Chrome is installed it is used automatically (best fingerprint);
otherwise Playwright's bundled Chromium is used.

## Usage

```bash
curl "http://localhost:8000/api/v1/search?engine=google_images&q=apple"
```

```python
import requests

response = requests.get("http://localhost:8000/api/v1/search", params={
    "engine": "google_images",
    "q": "apple",
    "color": "transparent",
    "image_type": "clipart",
    "size": "large",
})
for image in response.json()["images"]:
    print(image["original"]["link"], image["source"]["name"])
```

Interactive docs: http://localhost:8000/docs

## Parameters

| Parameter | Description |
|---|---|
| `engine` | Required. Must be `google_images`. |
| `q` | Required. Search query (supports operators like `site:`). |
| `device` | `desktop` (default), `mobile`, or `tablet`. |
| `location` / `uule` | Geographic targeting (location is auto-encoded to uule). |
| `gl` / `hl` | Country (default `us`) and interface language (default `en`). |
| `lr` / `cr` | Language / country restriction of documents. |
| `nfpr` | `1` to exclude auto-corrected results. |
| `filter` | `0` to disable duplicate-content filters. |
| `safe` | `active`, `blur` (default), or `off`. |
| `size` | `large`, `medium`, `icon`, `larger_than_2mp`, ... |
| `color` | `transparent`, `black_and_white`, `red`, `blue`, ... |
| `image_type` | `clipart`, `line_drawing`, `gif`, `face`, `photo`. |
| `time_period` | `last_hour` ... `last_year`. |
| `usage_rights` | `creative_commons_licenses`, `commercial_or_other_licenses`. |
| `aspect_ratio` | `square`, `tall`, `wide`, `panoramic`. |
| `tbs` | Raw Google filter string (overrides the friendly filters). |
| `page` | Page number, ~100 results per page. |
| `api_key` | Required when `API_KEYS` is configured (or `Authorization: Bearer`). |

## Response shape

```json
{
  "search_metadata":   { "id": "...", "status": "Success", "request_url": "...", "json_url": "...", "html_url": "..." },
  "search_parameters": { "engine": "google_images", "q": "apple", "...": "..." },
  "search_information":{ "query_displayed": "apple", "page": 1 },
  "suggestions":       [ { "title": "Fruit", "link": "..." } ],
  "images": [
    {
      "position": 1,
      "title": "Fresh Gala Apple, Each",
      "source":   { "name": "Walmart", "link": "https://www.walmart.com/ip/..." },
      "original": { "link": "https://i5.walmartimages.com/...", "width": 3000, "height": 3000 },
      "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=tbn:..."
    }
  ],
  "related_searches": [ { "query": "apple cartoon", "link": "...", "highlighted": ["cartoon"] } ]
}
```

Errors always use a consistent contract: `400` validation,
`401` bad API key, `429` Google rate limit / CAPTCHA, `500` internal,
`503` timeout — always as `{"error": "message"}`.

Recent searches are kept in memory and can be replayed via
`GET /api/v1/searches/{id}` (JSON) and `GET /api/v1/searches/{id}/html`
(raw page HTML).

## Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `API_KEYS` | *(empty — auth disabled)* | Comma-separated accepted API keys. |
| `REQUEST_TIMEOUT` | `90` | Seconds before returning 503. |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Base for `json_url`/`html_url`. |

## Testing

```bash
pytest tests/
```

## Notes & limitations

- Heavy traffic from one IP will eventually hit Google's CAPTCHA (the API
  returns `429`; one automatic retry is built in). For production volume,
  route the browser through rotating proxies.
- `total_results` is not exposed by Google's images UI and is omitted.
- Google's current images vertical ignores its own aspect-ratio filter, so
  `aspect_ratio` is enforced server-side from the original images'
  dimensions — filtered pages return fewer than 100 results.
- Scraping Google is against Google's ToS; use responsibly and at your own
  risk.
