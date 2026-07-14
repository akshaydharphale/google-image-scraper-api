"""Pydantic models mirroring the Google Images API OpenAPI schemas."""

from pydantic import BaseModel, ConfigDict


class SearchMetadata(BaseModel):
    id: str
    status: str
    created_at: str
    request_time_taken: float | None = None
    parsing_time_taken: float | None = None
    total_time_taken: float | None = None
    request_url: str | None = None
    html_url: str | None = None
    json_url: str | None = None


class SearchParameters(BaseModel):
    model_config = ConfigDict(extra="allow")

    engine: str = "google_images"
    q: str
    device: str | None = None
    uule: str | None = None
    location: str | None = None
    cr: str | None = None
    hl: str | None = None
    gl: str | None = None
    lr: str | None = None
    nfpr: int | None = None
    filter: int | None = None
    safe: str | None = None
    page: int | None = None
    tbs: str | None = None
    size: str | None = None
    color: str | None = None
    image_type: str | None = None
    time_period: str | None = None
    usage_rights: str | None = None
    aspect_ratio: str | None = None


class SearchInformation(BaseModel):
    query_displayed: str | None = None
    total_results: int | None = None
    page: int | None = None
    time_taken_displayed: float | None = None
    detected_location: str | None = None
    did_you_mean: str | None = None
    has_no_results_for: bool | None = None
    showing_results_for: str | None = None


class Suggestion(BaseModel):
    title: str
    link: str
    thumbnail: str | None = None


class ImageSource(BaseModel):
    name: str
    link: str


class OriginalImage(BaseModel):
    link: str
    width: int | None = None
    height: int | None = None


class Image(BaseModel):
    position: int
    title: str
    source: ImageSource
    original: OriginalImage
    thumbnail: str
    tag: str | None = None


class RelatedSearch(BaseModel):
    link: str
    query: str
    highlighted: list[str] | None = None
    thumbnail: str | None = None


class SearchResponse(BaseModel):
    model_config = ConfigDict(exclude_none=True)

    search_metadata: SearchMetadata
    search_parameters: SearchParameters
    search_information: SearchInformation | None = None
    suggestions: list[Suggestion] | None = None
    images: list[Image] | None = None
    related_searches: list[RelatedSearch] | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    error: str
