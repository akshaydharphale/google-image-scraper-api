"""Build the Google Images search URL from validated API parameters."""

from urllib.parse import urlencode

from app.params import SearchParams
from app.uule import encode_uule

GOOGLE_SEARCH = "https://www.google.com/search"


def build_search_url(params: SearchParams) -> str:
    query: dict[str, str] = {
        "q": params.q,
        "udm": "2",  # Google Images vertical
        "hl": params.hl,
        "gl": params.gl,
    }
    tbs = params.build_tbs()
    if tbs:
        query["tbs"] = tbs
    if params.lr:
        query["lr"] = params.lr
    if params.cr:
        query["cr"] = f"country{params.cr.upper()}"
    if params.nfpr:
        query["nfpr"] = str(params.nfpr)
    if params.filter == 0:
        query["filter"] = "0"
    # "blur" is Google's default; only pass explicit overrides.
    if params.safe == "active":
        query["safe"] = "active"
    elif params.safe == "off":
        query["safe"] = "off"
    uule = params.uule
    if not uule and params.location:
        uule = encode_uule(params.location)
    if uule:
        query["uule"] = uule
    return f"{GOOGLE_SEARCH}?{urlencode(query)}"


def build_chunk_url(params: SearchParams) -> str:
    """URL of Google's async image-batch endpoint, used for pages >= 2.

    This is the endpoint the images page itself pulls further result
    batches from. It returns an HTML chunk whose result divs carry flat
    data-* attributes (data-ou, data-pt, data-ru, ...).
    """
    page_index = params.page - 1
    base = build_search_url(params)
    base = base.replace("udm=2", "tbm=isch")
    extra = urlencode(
        {
            "asearch": "ichunklite",
            "async": "_id:islrg_c,_fmt:html",
            "start": str(page_index * 100),
            "ijn": str(page_index),
        }
    )
    return f"{base}&{extra}"
