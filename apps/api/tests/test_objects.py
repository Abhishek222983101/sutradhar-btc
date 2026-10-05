"""Object pages behind the omnibox: an AS number must open a page, and bad input must fail cleanly.

The tiny test world uses reserved documentation IPs, which have no AS, so the positive path (a real AS with IPs) is
checked against the live hero dataset by the end-to-end browser test; here the contract and the error paths."""

from __future__ import annotations

from fastapi.testclient import TestClient
from test_cases import _analysed


def test_asn_page_rejects_nonsense_and_unknown(client: TestClient, tiny_csv: bytes) -> None:
    headers, run_id = _analysed(client, tiny_csv)
    base = f"/api/v1/runs/{run_id}/asn"
    assert client.get(f"{base}/0", headers=headers).status_code == 422
    assert client.get(f"{base}/99999999999", headers=headers).status_code == 422
    assert client.get(f"{base}/15169", headers=headers).status_code == 404
    assert client.get(f"{base}/15169").status_code == 401


def test_asn_search_never_offers_a_dead_end(client: TestClient, tiny_csv: bytes) -> None:
    headers, run_id = _analysed(client, tiny_csv)
    hits = client.get(f"/api/v1/runs/{run_id}/search", headers=headers, params={"q": "AS15169"}).json()[
        "hits"
    ]
    assert not any(
        h["kind"] == "asn" for h in hits
    )  # no IP in this world is on that AS, so no hit is offered
