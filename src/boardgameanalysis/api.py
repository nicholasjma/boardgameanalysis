"""Client for the BoardGameGeek XML API2 ``thing`` endpoint.

BGG requires a registered application token for the XML API
(https://boardgamegeek.com/using_the_xml_api). Pass it explicitly or set ``BGG_TOKEN``.
"""

from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from boardgameanalysis import __version__

log = logging.getLogger(__name__)

BASE_URL = "https://boardgamegeek.com/xmlapi2"
MAX_IDS_PER_REQUEST = 20
# BGG's robots.txt asks for a 5 second crawl delay; we honor it for API calls too.
DEFAULT_DELAY_S = 5.0
_RETRY_STATUSES = {202, 429, 500, 502, 503, 504}


class BGGError(RuntimeError):
    """Raised when BGG returns something we cannot recover from."""


class BGGAuthError(BGGError):
    """Raised when the API token is missing or rejected."""


@dataclass(frozen=True, slots=True)
class Game:
    """One board game as returned by ``/thing?stats=1``."""

    game_id: int
    name: str
    year: int | None
    rank: int | None
    min_players: int | None
    max_players: int | None
    avg_time: int | None
    min_time: int | None
    max_time: int | None
    age: int | None
    avg_rating: float | None
    geek_rating: float | None
    num_votes: int | None
    owned: int | None
    weight: float | None
    image_url: str | None
    mechanics: tuple[str, ...] = field(default_factory=tuple)
    categories: tuple[str, ...] = field(default_factory=tuple)
    designers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def bgg_url(self) -> str:
        return f"https://boardgamegeek.com/boardgame/{self.game_id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _value(node: ET.Element | None, path: str) -> str | None:
    if node is None:
        return None
    el = node.find(path)
    if el is None:
        return None
    return el.get("value")


def _int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw not in (None, "") else None
    except ValueError:  # e.g. "Not Ranked"
        return None


def _float(raw: str | None) -> float | None:
    try:
        return float(raw) if raw not in (None, "") else None
    except ValueError:
        return None


def _positive(x: float | None) -> float | None:
    """BGG uses 0 for "no data" on ratings and weight."""
    return x if x else None


def parse_things(xml_text: str) -> list[Game]:
    """Parse a ``/thing`` response body into :class:`Game` records."""
    root = ET.fromstring(xml_text)
    games: list[Game] = []
    for item in root.iter("item"):
        if item.get("type") != "boardgame":
            continue
        links: dict[str, list[str]] = {}
        for link in item.iter("link"):
            links.setdefault(link.get("type", ""), []).append(link.get("value", ""))
        primary = item.find("name[@type='primary']")
        ratings = item.find("statistics/ratings")
        rank_raw = None
        if ratings is not None:
            rank_el = ratings.find("ranks/rank[@name='boardgame']")
            rank_raw = rank_el.get("value") if rank_el is not None else None
        image = item.findtext("image")
        games.append(
            Game(
                game_id=int(item.get("id", "0")),
                name=primary.get("value", "") if primary is not None else "",
                year=_int(_value(item, "yearpublished")),
                rank=_int(rank_raw),
                min_players=_int(_value(item, "minplayers")),
                max_players=_int(_value(item, "maxplayers")),
                avg_time=_int(_value(item, "playingtime")),
                min_time=_int(_value(item, "minplaytime")),
                max_time=_int(_value(item, "maxplaytime")),
                age=_int(_value(item, "minage")),
                avg_rating=_positive(_float(_value(ratings, "average"))),
                geek_rating=_positive(_float(_value(ratings, "bayesaverage"))),
                num_votes=_int(_value(ratings, "usersrated")),
                owned=_int(_value(ratings, "owned")),
                weight=_positive(_float(_value(ratings, "averageweight"))),
                image_url=image.strip() if image else None,
                mechanics=tuple(links.get("boardgamemechanic", ())),
                categories=tuple(links.get("boardgamecategory", ())),
                designers=tuple(links.get("boardgamedesigner", ())),
            )
        )
    return games


def _chunks(ids: Sequence[int], size: int) -> Iterator[Sequence[int]]:
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


class BGGClient:
    """Rate-limited, retrying client for BGG's XML API2."""

    def __init__(
        self,
        token: str | None = None,
        *,
        delay_s: float = DEFAULT_DELAY_S,
        max_retries: int = 6,
        timeout_s: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        token = token or os.environ.get("BGG_TOKEN")
        if not token:
            raise BGGAuthError(
                "A BGG API token is required. Register an application at "
                "https://boardgamegeek.com/using_the_xml_api and set BGG_TOKEN."
            )
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": f"boardgameanalysis/{__version__} (+https://github.com/nicholasjma/boardgameanalysis)",
            },
            timeout=timeout_s,
            transport=transport,
        )
        self._delay_s = delay_s
        self._max_retries = max_retries
        self._sleep = sleep
        self._last_request = 0.0

    def __enter__(self) -> BGGClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _throttle(self) -> None:
        wait = self._last_request + self._delay_s - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()

    def _get(self, path: str, params: dict[str, str]) -> str:
        backoff = max(self._delay_s, 1.0)
        for attempt in range(self._max_retries + 1):
            self._throttle()
            try:
                resp = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                log.warning("Network error (%s), retrying", exc)
            else:
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code in (401, 403):
                    raise BGGAuthError(f"BGG rejected the API token (HTTP {resp.status_code}).")
                if resp.status_code not in _RETRY_STATUSES:
                    raise BGGError(f"HTTP {resp.status_code} from BGG: {resp.text[:200]}")
                retry_after = _float(resp.headers.get("Retry-After"))
                if retry_after:
                    backoff = max(backoff, retry_after)
                log.info("HTTP %s from BGG, backing off %.0fs", resp.status_code, backoff)
            if attempt < self._max_retries:
                self._sleep(backoff)
                backoff = min(backoff * 2, 300)
        raise BGGError(f"Gave up on {path} after {self._max_retries + 1} attempts")

    def iter_games(self, ids: Iterable[int]) -> Iterator[list[Game]]:
        """Yield parsed games one batch (≤20 IDs) at a time."""
        for batch in _chunks(list(ids), MAX_IDS_PER_REQUEST):
            xml_text = self._get(
                "/thing",
                {"id": ",".join(map(str, batch)), "type": "boardgame", "stats": "1"},
            )
            yield parse_things(xml_text)
