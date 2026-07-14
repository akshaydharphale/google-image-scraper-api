"""Extract structured results from a rendered Google Images page.

Google embeds per-result metadata as JSON arrays of the form:

    [0, "<docid>",
        ["<thumbnail_url>", <height>, <width>],
        ["<original_url>", <height>, <width>],
        ...,
        {"2000": [null, "<domain>", "<filesize>"],
         "2003": [null, "<id>", "<page_url>", "<title>", ..., "<source>"],
         ...}]

Each result appears more than once in the page data (different view
models reference the same docid), so results are deduplicated by docid
while preserving order of first appearance.
"""

import html as html_lib
import json
import re
from urllib.parse import parse_qs, urlparse

from app.models import Image, ImageSource, OriginalImage, RelatedSearch, Suggestion

_RESULT_START = re.compile(r'\[[01],"[\w\-]{5,40}",\["https?://')
_GOOGLE = "https://www.google.com"


def _balanced_array(s: str, start: int) -> str | None:
    """Return the JSON array starting at s[start], honoring string escapes."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, min(len(s), start + 200_000)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return None


def _first_dict(node: list) -> dict | None:
    for item in node:
        if isinstance(item, dict):
            return item
    return None


def _is_url_triplet(v) -> bool:
    return (
        isinstance(v, list)
        and len(v) >= 3
        and isinstance(v[0], str)
        and v[0].startswith("http")
        and isinstance(v[1], int)
        and isinstance(v[2], int)
    )


def parse_images(page_html: str) -> list[Image]:
    images: list[Image] = []
    seen: set[str] = set()
    for match in _RESULT_START.finditer(page_html):
        raw = _balanced_array(page_html, match.start())
        if not raw:
            continue
        try:
            node = json.loads(raw)
        except (json.JSONDecodeError, RecursionError):
            continue
        if len(node) < 4 or not _is_url_triplet(node[2]) or not _is_url_triplet(node[3]):
            continue
        docid = node[1]
        if not isinstance(docid, str) or docid in seen:
            continue
        meta = _first_dict(node)
        info = (meta or {}).get("2003")
        if not isinstance(info, list) or len(info) < 4:
            continue
        page_url = info[2]
        title = info[3]
        if not page_url or not title:
            continue
        source_name = None
        if len(info) > 12 and isinstance(info[12], str):
            source_name = info[12]
        if not source_name:
            domain_info = (meta or {}).get("2000")
            if isinstance(domain_info, list) and len(domain_info) > 1:
                source_name = domain_info[1]
        if not source_name:
            source_name = urlparse(page_url).netloc
        thumb_url, _, _ = node[2][0], node[2][1], node[2][2]
        orig_url, orig_h, orig_w = node[3][0], node[3][1], node[3][2]
        seen.add(docid)
        images.append(
            Image(
                position=len(images) + 1,
                title=title,
                source=ImageSource(name=source_name, link=page_url),
                original=OriginalImage(link=orig_url, width=orig_w, height=orig_h),
                thumbnail=thumb_url,
            )
        )
    return images


_CHUNK_DIV = re.compile(r'<div[^>]+data-ou="[^"]+"[^>]*>')
_DATA_ATTR = re.compile(r'data-([a-z]+)="([^"]*)"')


def parse_images_chunk(chunk_html: str) -> list[Image]:
    """Parse Google's async batch endpoint format (pages >= 2).

    Result divs carry flat attributes: data-ou (original URL), data-oh /
    data-ow (dimensions), data-pt (title), data-ru (source page URL),
    data-st (source name), data-pu (thumbnail URL).
    """
    images: list[Image] = []
    seen: set[str] = set()
    for match in _CHUNK_DIV.finditer(chunk_html):
        attrs = {k: html_lib.unescape(v) for k, v in _DATA_ATTR.findall(match.group(0))}
        orig = attrs.get("ou")
        docid = attrs.get("docid") or orig
        if not orig or docid in seen:
            continue
        page_url = attrs.get("ru")
        title = attrs.get("pt")
        if not page_url or not title:
            continue
        seen.add(docid)
        source_name = attrs.get("st") or urlparse(page_url).netloc
        images.append(
            Image(
                position=len(images) + 1,
                title=title,
                source=ImageSource(name=source_name, link=page_url),
                original=OriginalImage(
                    link=orig,
                    width=int(attrs["ow"]) if attrs.get("ow", "").isdigit() else None,
                    height=int(attrs["oh"]) if attrs.get("oh", "").isdigit() else None,
                ),
                thumbnail=attrs.get("pu") or attrs.get("thu") or "",
            )
        )
    return images


_ANCHOR = re.compile(
    r'<a[^>]+href="(/search\?[^"]*)"[^>]*>(.*?)</a>', re.DOTALL
)
_TAG = re.compile(r"<[^>]+>")
_IMG_SRC = re.compile(r'<img[^>]+src="([^"]+)"')


def parse_suggestions(page_html: str, query: str) -> list[Suggestion]:
    """Refinement chips: /search links whose q extends the original query."""
    suggestions: list[Suggestion] = []
    seen: set[str] = set()
    q_norm = query.strip().lower()
    for href, inner in _ANCHOR.findall(page_html):
        href = html_lib.unescape(href)
        params = parse_qs(urlparse(href).query)
        chip_q = (params.get("q") or [""])[0]
        if not chip_q or chip_q.strip().lower() == q_norm:
            continue
        if q_norm not in chip_q.lower():
            continue
        title = html_lib.unescape(_TAG.sub("", inner)).strip()
        if not title or len(title) > 60 or title.lower() in seen:
            continue
        seen.add(title.lower())
        thumb_match = _IMG_SRC.search(inner)
        suggestions.append(
            Suggestion(
                title=title,
                link=f"{_GOOGLE}{href}",
                thumbnail=html_lib.unescape(thumb_match.group(1)) if thumb_match else None,
            )
        )
    return suggestions


def parse_related_searches(page_html: str, query: str) -> list[RelatedSearch]:
    """Related queries: /search links to different (non-superset) queries."""
    related: list[RelatedSearch] = []
    seen: set[str] = set()
    q_norm = query.strip().lower()
    q_words = set(q_norm.split())
    for href, inner in _ANCHOR.findall(page_html):
        href = html_lib.unescape(href)
        params = parse_qs(urlparse(href).query)
        rel_q = (params.get("q") or [""])[0]
        rel_norm = rel_q.strip().lower()
        if not rel_q or rel_norm == q_norm or rel_norm in seen:
            continue
        # Must be an images search and share at least one word with the query.
        if (params.get("udm") or [""])[0] != "2":
            continue
        if not (q_words & set(rel_norm.split())):
            continue
        title = html_lib.unescape(_TAG.sub("", inner)).strip()
        if not title:
            continue
        seen.add(rel_norm)
        highlighted = [w for w in rel_norm.split() if w not in q_words]
        related.append(
            RelatedSearch(
                link=f"{_GOOGLE}{href}",
                query=rel_q,
                highlighted=highlighted or None,
            )
        )
    return related


_DID_YOU_MEAN = re.compile(
    r"Did you mean.*?<a[^>]*>(.*?)</a>", re.DOTALL | re.IGNORECASE
)
_SHOWING_FOR = re.compile(
    r"Showing results for.*?<a[^>]*>(.*?)</a>", re.DOTALL | re.IGNORECASE
)


def parse_spelling(page_html: str) -> dict:
    out: dict = {}
    m = _DID_YOU_MEAN.search(page_html)
    if m:
        out["did_you_mean"] = html_lib.unescape(_TAG.sub("", m.group(1))).strip()
    m = _SHOWING_FOR.search(page_html)
    if m:
        out["showing_results_for"] = html_lib.unescape(_TAG.sub("", m.group(1))).strip()
    return out
