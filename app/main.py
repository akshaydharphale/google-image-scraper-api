"""Google Images API — a self-hosted image search API."""

import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse

from app.auth import require_api_key
from app.config import get_settings
from app.models import (
    ErrorResponse,
    SearchInformation,
    SearchMetadata,
    SearchParameters,
    SearchResponse,
)
from app.params import SearchParams
from app.scraper.fetcher import BlockedError, fetcher
from app.scraper.parser import (
    parse_images,
    parse_images_chunk,
    parse_related_searches,
    parse_spelling,
    parse_suggestions,
)
from app.scraper.url_builder import build_chunk_url, build_search_url
from app.store import new_search_id, store, utc_now_iso

RESULTS_PER_PAGE = 100


def _matches_aspect_ratio(ratio: str, width: int | None, height: int | None) -> bool:
    if not width or not height:
        return False
    r = width / height
    if ratio == "square":
        return 0.9 <= r <= 1.1
    if ratio == "tall":
        return r < 0.9
    if ratio == "wide":
        return r > 1.1
    if ratio == "panoramic":
        return r >= 2.0
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    await fetcher.startup()
    yield
    await fetcher.shutdown()


app = FastAPI(
    title="Google Images API",
    description=(
        "Scrape Google Images: high-resolution image URLs, source details, "
        "thumbnails, and related searches. Filter by size, color, type, "
        "usage rights, time period, and aspect ratio."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    loc = ".".join(str(p) for p in first.get("loc", []) if p != "query")
    msg = first.get("msg", "Invalid request parameters.")
    return JSONResponse(status_code=400, content={"error": f"{loc}: {msg}".strip(": ")})


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.get(
    "/api/v1/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    dependencies=[Depends(require_api_key)],
)
async def search(params: SearchParams = Depends()) -> JSONResponse:
    settings = get_settings()
    search_id = new_search_id()
    created_at = utc_now_iso()
    request_url = build_search_url(params)
    started = time.monotonic()

    chunk_url = build_chunk_url(params) if params.page > 1 else None

    try:
        page_html, chunk_html = await asyncio.wait_for(
            fetcher.fetch(
                request_url,
                device=params.device,
                hl=params.hl,
                chunk_url=chunk_url,
                timeout=settings.request_timeout,
            ),
            timeout=settings.request_timeout,
        )
    except (asyncio.TimeoutError, TimeoutError):
        raise HTTPException(503, "We could not retrieve results in 90 seconds.")
    except BlockedError as exc:
        raise HTTPException(429, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Failed to retrieve results: {exc}")

    request_time = round(time.monotonic() - started, 2)
    parse_started = time.monotonic()

    if params.page == 1:
        page_images = parse_images(page_html)
    else:
        page_images = parse_images_chunk(chunk_html or "")

    # Google's images vertical (udm=2) ignores the iar: filter, so the
    # aspect ratio is enforced here from the originals' dimensions.
    if params.aspect_ratio:
        page_images = [
            img
            for img in page_images
            if _matches_aspect_ratio(
                params.aspect_ratio, img.original.width, img.original.height
            )
        ]
        for i, img in enumerate(page_images):
            img.position = i + 1

    suggestions = parse_suggestions(page_html, params.q) if params.page == 1 else []
    related = parse_related_searches(page_html, params.q) if params.page == 1 else []
    spelling = parse_spelling(page_html)

    parsing_time = round(time.monotonic() - parse_started, 2)
    base = settings.public_base_url.rstrip("/")

    response = SearchResponse(
        search_metadata=SearchMetadata(
            id=search_id,
            status="Success",
            created_at=created_at,
            request_time_taken=request_time,
            parsing_time_taken=parsing_time,
            total_time_taken=round(request_time + parsing_time, 2),
            request_url=request_url,
            html_url=f"{base}/api/v1/searches/{search_id}/html",
            json_url=f"{base}/api/v1/searches/{search_id}",
        ),
        search_parameters=SearchParameters(**params.echo()),
        search_information=SearchInformation(
            query_displayed=params.q,
            page=params.page,
            has_no_results_for=not page_images or None,
            **spelling,
        ),
        suggestions=suggestions or None,
        images=page_images or None,
        related_searches=related or None,
    )
    body = response.model_dump(exclude_none=True)
    store.put(search_id, body, page_html)
    return JSONResponse(content=body)


@app.get(
    "/api/v1/searches/{search_id}",
    dependencies=[Depends(require_api_key)],
    responses={404: {"model": ErrorResponse}},
)
async def get_search_json(search_id: str) -> JSONResponse:
    item = store.get(search_id)
    if not item:
        raise HTTPException(404, "Search not found (results are kept in memory only).")
    return JSONResponse(content=item.json_body)


@app.get(
    "/api/v1/searches/{search_id}/html",
    dependencies=[Depends(require_api_key)],
    responses={404: {"model": ErrorResponse}},
)
async def get_search_html(search_id: str) -> HTMLResponse:
    item = store.get(search_id)
    if not item:
        raise HTTPException(404, "Search not found (results are kept in memory only).")
    return HTMLResponse(content=item.html)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
