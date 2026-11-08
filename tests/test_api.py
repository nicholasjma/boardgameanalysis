from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from boardgameanalysis.api import BGGAuthError, BGGClient, BGGError, parse_things

FIXTURE = (Path(__file__).parent / "fixtures" / "thing.xml").read_text(encoding="utf-8")


def test_parse_things_extracts_fields() -> None:
    games = parse_things(FIXTURE)
    assert [g.game_id for g in games] == [174430, 999]  # expansion skipped

    g = games[0]
    assert g.name == "Gloomhaven"
    assert g.rank == 3
    assert (g.min_players, g.max_players, g.avg_time, g.age) == (1, 4, 120, 14)
    assert g.avg_rating == pytest.approx(8.58)
    assert g.weight == pytest.approx(3.91)
    assert g.num_votes == 63000
    assert g.mechanics == ("Cooperative Game", "I Cut, You Choose")
    assert g.categories == ("Adventure", "Fantasy")
    assert g.designers == ("Isaac Childres",)
    assert g.bgg_url == "https://boardgamegeek.com/boardgame/174430"


def test_parse_things_handles_unranked_and_zeroes() -> None:
    g = parse_things(FIXTURE)[1]
    assert g.rank is None
    assert g.avg_rating is None
    assert g.weight is None
    assert g.mechanics == ()


def _client(handler: httpx.MockTransport, **kw: object) -> BGGClient:
    return BGGClient("tok", delay_s=0, transport=handler, sleep=lambda _s: None, **kw)  # type: ignore[arg-type]


def test_client_batches_and_sends_token() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=FIXTURE)

    with _client(httpx.MockTransport(handle)) as client:
        batches = list(client.iter_games(range(45)))

    assert len(batches) == 3
    assert [len(r.url.params["id"].split(",")) for r in seen] == [20, 20, 5]
    assert seen[0].headers["Authorization"] == "Bearer tok"
    assert seen[0].url.params["stats"] == "1"


def test_client_retries_then_succeeds() -> None:
    responses = iter([httpx.Response(429), httpx.Response(202), httpx.Response(200, text=FIXTURE)])

    with _client(httpx.MockTransport(lambda _r: next(responses))) as client:
        (batch,) = client.iter_games([174430])
    assert batch[0].name == "Gloomhaven"


def test_client_gives_up() -> None:
    with (
        _client(httpx.MockTransport(lambda _r: httpx.Response(503)), max_retries=2) as client,
        pytest.raises(BGGError, match="Gave up"),
    ):
        list(client.iter_games([1]))


def test_client_auth_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BGG_TOKEN", raising=False)
    with pytest.raises(BGGAuthError, match="token is required"):
        BGGClient()

    with (
        _client(httpx.MockTransport(lambda _r: httpx.Response(401))) as client,
        pytest.raises(BGGAuthError, match="rejected"),
    ):
        list(client.iter_games([1]))
