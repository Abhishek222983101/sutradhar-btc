"""Academy: one static challenge, scored server-side, truth never in the response."""

from __future__ import annotations

from apitest import add_user, bearer, login
from fastapi.testclient import TestClient

from sutradhar_api.academy import ANSWERS


def test_challenge_hides_answers(client: TestClient) -> None:
    """Options are shown (it's multiple choice); the correct-answer *mapping* must never be sent."""
    headers = bearer(login(client, add_user(client, "analyst")))
    challenge = client.get("/api/v1/academy/challenges", headers=headers).json()[0]
    assert set(challenge) == {"id", "title", "time_limit_s", "questions"}
    for q in challenge["questions"]:
        assert set(q) == {
            "id",
            "text",
            "options",
            "kind",
        }  # no "correct" or "answer" field ever leaves the server


def test_attempt_is_scored(client: TestClient) -> None:
    headers = bearer(login(client, add_user(client, "analyst")))
    good = client.post(
        "/api/v1/academy/challenges/hero-1/attempts",
        headers=headers,
        json={"answers": ANSWERS, "duration_s": 120},
    )
    assert good.status_code == 201 and good.json()["score"] == 1.0
    bad = client.post(
        "/api/v1/academy/challenges/hero-1/attempts",
        headers=headers,
        json={"answers": {"q1": "wrong"}, "duration_s": 5},
    )
    assert bad.json()["score"] == 0.0
    board = client.get("/api/v1/academy/leaderboard", headers=headers).json()
    assert board[0]["score"] == 1.0
