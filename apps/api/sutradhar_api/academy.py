"""Academy: one static challenge over the hero world (scope-cut fallback per the blueprint — a full generator-driven
challenge system was cut for time; this keeps the judge-facing feature). Truth never reaches the client: scoring
happens server-side against answers baked in at build time from the hero world's ground truth.
"""

from __future__ import annotations

# Answers were read once from the hero world's truth files at generation time; the client never sees them.
CHALLENGE = {
    "id": "hero-1",
    "title": "Find the ransomware operator",
    "time_limit_s": 600,
    "questions": [
        {
            "id": "q1",
            "text": "Which lead type is used for a wallet cluster judged by the ranker?",
            "options": ["ACTOR", "CASHOUT", "CHAIN", "TX"],
            "kind": "single",
        },
        {
            "id": "q2",
            "text": "What does invariant I8 guarantee about CoinJoin transactions?",
            "options": [
                "Their inputs are never merged into one wallet cluster",
                "They are always flagged as illicit",
                "They are excluded from the dataset",
                "Their fees are ignored",
            ],
            "kind": "single",
        },
        {
            "id": "q3",
            "text": "In the risk-propagation model, what happens to taint that reaches an exchange (a 'service')?",
            "options": [
                "It is recorded there but does not propagate further",
                "It doubles",
                "It is deleted immediately",
                "It propagates to every customer of the exchange",
            ],
            "kind": "single",
        },
        {
            "id": "q4",
            "text": "A lead is graded A when it has p >= 0.8 and at least how many independent evidence families?",
            "options": ["1", "2", "3", "5"],
            "kind": "single",
        },
        {
            "id": "q5",
            "text": "What does the counterfactual on a lead show?",
            "options": [
                "What the score would be if the strongest evidence were reset to a typical clean value",
                "The lead's history across previous runs",
                "A list of similar leads",
                "The exact identity of the wallet's owner",
            ],
            "kind": "single",
        },
    ],
}
ANSWERS = {
    "q1": "ACTOR",
    "q2": "Their inputs are never merged into one wallet cluster",
    "q3": "It is recorded there but does not propagate further",
    "q4": "3",
    "q5": "What the score would be if the strongest evidence were reset to a typical clean value",
}


def score(answers: dict[str, str]) -> tuple[float, dict[str, bool]]:
    per = {qid: answers.get(qid) == correct for qid, correct in ANSWERS.items()}
    return sum(per.values()) / len(ANSWERS), per


def public_challenge() -> dict:
    return CHALLENGE
