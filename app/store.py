"""Bounded in-memory store of recent searches, backing html_url/json_url."""

import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone


def new_search_id() -> str:
    return f"search_{secrets.token_urlsafe(18)}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class StoredSearch:
    json_body: dict
    html: str
    created_at: str = field(default_factory=utc_now_iso)


class SearchStore:
    def __init__(self, max_size: int = 100):
        self._max_size = max_size
        self._items: OrderedDict[str, StoredSearch] = OrderedDict()

    def put(self, search_id: str, json_body: dict, html: str) -> None:
        self._items[search_id] = StoredSearch(json_body=json_body, html=html)
        while len(self._items) > self._max_size:
            self._items.popitem(last=False)

    def get(self, search_id: str) -> StoredSearch | None:
        return self._items.get(search_id)


store = SearchStore()
