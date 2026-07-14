"""Query-parameter validation and Google `tbs` filter construction."""

from typing import Literal

from fastapi import Query
from pydantic import BaseModel

Device = Literal["desktop", "mobile", "tablet"]
Safe = Literal["active", "blur", "off"]

Size = Literal[
    "large", "medium", "icon",
    "larger_than_400x300", "larger_than_640x480", "larger_than_800x600",
    "larger_than_1024x768", "larger_than_2mp", "larger_than_4mp",
    "larger_than_6mp", "larger_than_8mp", "larger_than_12mp",
    "larger_than_15mp", "larger_than_20mp", "larger_than_40mp",
    "larger_than_70mp",
]
Color = Literal[
    "black_and_white", "color", "transparent", "red", "orange", "yellow",
    "green", "teal", "blue", "purple", "pink", "white", "gray", "black",
    "brown",
]
ImageType = Literal["clipart", "line_drawing", "gif", "face", "photo"]
TimePeriod = Literal["last_hour", "last_day", "last_week", "last_month", "last_year"]
UsageRights = Literal["creative_commons_licenses", "commercial_or_other_licenses"]
AspectRatio = Literal["square", "tall", "wide", "panoramic"]

_SIZE_TBS = {
    "large": "isz:l",
    "medium": "isz:m",
    "icon": "isz:i",
    "larger_than_400x300": "isz:lt,islt:qsvga",
    "larger_than_640x480": "isz:lt,islt:vga",
    "larger_than_800x600": "isz:lt,islt:svga",
    "larger_than_1024x768": "isz:lt,islt:xga",
    "larger_than_2mp": "isz:lt,islt:2mp",
    "larger_than_4mp": "isz:lt,islt:4mp",
    "larger_than_6mp": "isz:lt,islt:6mp",
    "larger_than_8mp": "isz:lt,islt:8mp",
    "larger_than_12mp": "isz:lt,islt:12mp",
    "larger_than_15mp": "isz:lt,islt:15mp",
    "larger_than_20mp": "isz:lt,islt:20mp",
    "larger_than_40mp": "isz:lt,islt:40mp",
    "larger_than_70mp": "isz:lt,islt:70mp",
}
_COLOR_TBS = {
    "black_and_white": "ic:gray",
    "color": "ic:color",
    "transparent": "ic:trans",
}
_SPECIFIC_COLORS = {
    "red", "orange", "yellow", "green", "teal", "blue", "purple", "pink",
    "white", "gray", "black", "brown",
}
_TYPE_TBS = {
    "clipart": "itp:clipart",
    "line_drawing": "itp:lineart",
    "gif": "itp:animated",
    "face": "itp:face",
    "photo": "itp:photo",
}
_TIME_TBS = {
    "last_hour": "qdr:h",
    "last_day": "qdr:d",
    "last_week": "qdr:w",
    "last_month": "qdr:m",
    "last_year": "qdr:y",
}
_RIGHTS_TBS = {
    "creative_commons_licenses": "sur:cl",
    "commercial_or_other_licenses": "sur:ol",
}
_ASPECT_TBS = {
    "square": "iar:s",
    "tall": "iar:t",
    "wide": "iar:w",
    "panoramic": "iar:xw",
}


class SearchParams(BaseModel):
    engine: Literal["google_images"]
    q: str
    device: Device = "desktop"
    location: str | None = None
    uule: str | None = None
    gl: str = "us"
    hl: str = "en"
    lr: str | None = None
    cr: str | None = None
    nfpr: Literal[0, 1] = 0
    filter: Literal[0, 1] = 1
    safe: Safe = "blur"
    tbs: str | None = None
    size: Size | None = None
    color: Color | None = None
    image_type: ImageType | None = None
    time_period: TimePeriod | None = None
    usage_rights: UsageRights | None = None
    aspect_ratio: AspectRatio | None = None
    page: int = Query(default=1, ge=1)

    def build_tbs(self) -> str | None:
        """Compose the Google `tbs` filter string from the friendly params.

        An explicit `tbs` value takes precedence over the individual filters.
        """
        if self.tbs:
            return self.tbs
        parts: list[str] = []
        if self.size:
            parts.append(_SIZE_TBS[self.size])
        if self.color:
            if self.color in _SPECIFIC_COLORS:
                parts.append(f"ic:specific,isc:{self.color}")
            else:
                parts.append(_COLOR_TBS[self.color])
        if self.image_type:
            parts.append(_TYPE_TBS[self.image_type])
        if self.time_period:
            parts.append(_TIME_TBS[self.time_period])
        if self.usage_rights:
            parts.append(_RIGHTS_TBS[self.usage_rights])
        if self.aspect_ratio:
            parts.append(_ASPECT_TBS[self.aspect_ratio])
        return ",".join(parts) if parts else None

    def echo(self) -> dict:
        """Parameters as echoed back in the `search_parameters` block."""
        out = {
            "engine": self.engine,
            "q": self.q,
            "device": self.device,
            "hl": self.hl,
            "gl": self.gl,
        }
        for field in (
            "location", "uule", "lr", "cr", "safe", "size", "color",
            "image_type", "time_period", "usage_rights", "aspect_ratio",
        ):
            value = getattr(self, field)
            if value is not None:
                out[field] = value
        if self.nfpr:
            out["nfpr"] = self.nfpr
        if self.filter != 1:
            out["filter"] = self.filter
        if self.page != 1:
            out["page"] = self.page
        tbs = self.build_tbs()
        if tbs:
            out["tbs"] = tbs
        return out
