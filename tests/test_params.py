import pytest
from pydantic import ValidationError

from app.params import SearchParams
from app.scraper.url_builder import build_chunk_url, build_search_url
from app.uule import encode_uule


def make(**overrides) -> SearchParams:
    base = {"engine": "google_images", "q": "apple"}
    base.update(overrides)
    return SearchParams(**base)


def test_tbs_composed_from_filters():
    params = make(size="large", color="transparent", image_type="clipart")
    assert params.build_tbs() == "isz:l,ic:trans,itp:clipart"


def test_tbs_specific_color():
    assert make(color="red").build_tbs() == "ic:specific,isc:red"


def test_explicit_tbs_wins():
    assert make(tbs="isz:m", size="large").build_tbs() == "isz:m"


def test_no_filters_no_tbs():
    assert make().build_tbs() is None


def test_invalid_engine_rejected():
    with pytest.raises(ValidationError):
        make(engine="google")


def test_invalid_size_rejected():
    with pytest.raises(ValidationError):
        make(size="tiny")


def test_search_url_contains_udm2():
    url = build_search_url(make(time_period="last_week"))
    assert "udm=2" in url and "qdr%3Aw" in url


def test_chunk_url_pagination():
    url = build_chunk_url(make(page=3))
    assert "tbm=isch" in url and "start=200" in url and "ijn=2" in url
    assert "udm=2" not in url


def test_location_encoded_as_uule():
    url = build_search_url(make(location="New York,New York,United States"))
    assert "uule=w%2BCAIQICI" in url


def test_uule_roundtrip_shape():
    value = encode_uule("Berlin,Germany")
    assert value.startswith("w+CAIQICI")
