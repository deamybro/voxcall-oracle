from __future__ import annotations

from typing import Any


def explain_decision(decision: dict[str, Any]) -> str:
    action = str(decision.get("action", "hold")).upper()
    ticker = decision.get("ticker", "AAPLx")
    confidence = decision.get("confidence", 0)
    sentiment = decision.get("sentiment", "neutral")
    reason = decision.get("reason", "No reason supplied.")
    return f"{action} {ticker} with {confidence}% confidence. Sentiment is {sentiment}. {reason}"


def format_vote_table(decision: dict[str, Any]) -> list[dict[str, Any]]:
    votes = decision.get("votes", [])
    if not isinstance(votes, list):
        return []
    return [
        {
            "model": index + 1,
            "action": vote.get("action", "hold"),
            "sentiment": vote.get("sentiment", "neutral"),
            "confidence": vote.get("confidence", 0),
            "ticker": vote.get("ticker", ""),
            "reason": vote.get("reason", ""),
        }
        for index, vote in enumerate(votes)
        if isinstance(vote, dict)
    ]
