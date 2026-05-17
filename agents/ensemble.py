from __future__ import annotations

import asyncio
import ast
import json
import os
import re
from collections import Counter
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_MODELS = [
    "DragonLLM/Llama-Open-Finance-8B",
    "AdaptLLM/finance-chat",
    "TheFinAI/Fin-o1-8B",
]

OUTDATED_MODEL_REPLACEMENTS = {
    "DragonLLM/Llama-Pro-Finance-70B-FP8": "DragonLLM/Llama-Open-Finance-8B",
    "FinGPT/fingpt-mt-13b": "TheFinAI/Fin-o1-8B",
}

FALLBACK_TICKERS = {
    "apple": "AAPLx",
    "aapl": "AAPLx",
    "tesla": "TSLAx",
    "tsla": "TSLAx",
    "nvidia": "NVDAx",
    "nvda": "NVDAx",
    "microsoft": "MSFTx",
    "msft": "MSFTx",
    "amazon": "AMZNx",
    "amzn": "AMZNx",
    "google": "GOOGLx",
    "alphabet": "GOOGLx",
    "meta": "METAx",
}

BULLISH_TERMS = {
    "beat",
    "raised",
    "growth",
    "record",
    "margin expansion",
    "strong demand",
    "guidance up",
    "accelerating",
    "profitable",
}

BEARISH_TERMS = {
    "miss",
    "lowered",
    "decline",
    "weak demand",
    "margin pressure",
    "guidance down",
    "lawsuit",
    "slowing",
    "loss",
}


def _client() -> OpenAI | None:
    api_key = os.getenv("FEATHERLESS_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        base_url=os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"),
        api_key=api_key,
        timeout=45,
    )


def configured_models() -> list[str]:
    raw_models = os.getenv("FEATHERLESS_MODELS", "")
    models = [model.strip() for model in raw_models.split(",") if model.strip()]
    if not models:
        return DEFAULT_MODELS
    normalized = [OUTDATED_MODEL_REPLACEMENTS.get(model, model) for model in models]
    seen = set()
    return [model for model in normalized if not (model in seen or seen.add(model))]


def _coerce_action(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\b(buy|long|bullish)\b", lowered):
        return "buy"
    if re.search(r"\b(sell|short|bearish)\b", lowered):
        return "sell"
    return "hold"


def _coerce_sentiment(text: str, action: str) -> str:
    lowered = text.lower()
    if "bullish" in lowered or action == "buy":
        return "bullish"
    if "bearish" in lowered or action == "sell":
        return "bearish"
    return "neutral"


def _coerce_confidence(text: str) -> int:
    percent_match = re.search(r"(\d{1,3})\s*%", text)
    number_match = percent_match or re.search(r'"?confidence"?\s*[:=]\s*"?(\d{1,3})', text, flags=re.IGNORECASE)
    if number_match:
        return max(0, min(int(number_match.group(1)), 100))
    return 72


def _coerce_ticker(text: str) -> str:
    ticker_match = re.search(r"\b([A-Z]{2,6}x)\b", text)
    if ticker_match:
        return ticker_match.group(1)
    lowered = text.lower()
    for key, symbol in FALLBACK_TICKERS.items():
        if key in lowered:
            return symbol
    return "AAPLx"


def _extract_json(content: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        try:
            payload = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            return None
    return payload if isinstance(payload, dict) else None


def _parse_vote_content(content: str, model: str) -> dict[str, Any] | None:
    parsed = _extract_json(content)
    if parsed:
        vote = _normalize_vote(parsed)
        vote["model"] = model
        return vote

    if not content.strip():
        return None

    action = _coerce_action(content)
    confidence = _coerce_confidence(content)
    vote = {
        "sentiment": _coerce_sentiment(content, action),
        "confidence": confidence,
        "action": action,
        "ticker": _coerce_ticker(content),
        "reason": content.strip().replace("\n", " ")[:240],
        "model": model,
    }
    return _normalize_vote(vote) | {"model": model}


def _normalize_vote(vote: dict[str, Any]) -> dict[str, Any]:
    action = str(vote.get("action", "hold")).lower()
    if action not in {"buy", "sell", "hold"}:
        action = "hold"

    sentiment = str(vote.get("sentiment", "neutral")).lower()
    if sentiment not in {"bullish", "bearish", "neutral"}:
        sentiment = "neutral"

    try:
        confidence = int(float(vote.get("confidence", 0)))
    except (TypeError, ValueError):
        confidence = 0

    return {
        "sentiment": sentiment,
        "confidence": max(0, min(confidence, 100)),
        "action": action,
        "ticker": str(vote.get("ticker", "AAPLx")),
        "reason": str(vote.get("reason", "No rationale returned."))[:240],
    }


def _fallback_analysis(transcript_chunk: str, current_prices: dict[str, float]) -> dict[str, Any]:
    text = transcript_chunk.lower()
    bullish = sum(1 for term in BULLISH_TERMS if term in text)
    bearish = sum(1 for term in BEARISH_TERMS if term in text)

    ticker = next((symbol for key, symbol in FALLBACK_TICKERS.items() if key in text), None)
    if ticker is None:
        ticker = next(iter(current_prices.keys()), "AAPLx")

    if bullish > bearish:
        action = "buy"
        sentiment = "bullish"
    elif bearish > bullish:
        action = "sell"
        sentiment = "bearish"
    else:
        action = "hold"
        sentiment = "neutral"

    confidence = min(90, 45 + abs(bullish - bearish) * 15)
    if action == "hold":
        confidence = 35

    return {
        "action": action,
        "sentiment": sentiment,
        "confidence": confidence,
        "ticker": ticker,
        "reason": "Demo heuristic used because Featherless API key is not configured.",
        "votes": [],
        "mode": "demo",
    }


async def _model_vote(client: OpenAI, model: str, transcript_chunk: str, current_prices: dict[str, float]) -> dict[str, Any] | None:
    prompt = f"""
You are a hedge-fund analyst trading tokenized xStocks.

Transcript:
{transcript_chunk}

Current xStock prices:
{json.dumps(current_prices, sort_keys=True)}

Return compact valid JSON only. Do not use Markdown. Do not include prose before or after the JSON.

JSON keys:
sentiment: bullish, bearish, or neutral
confidence: integer 0-100
action: buy, sell, or hold
ticker: xStock symbol such as AAPLx, TSLAx, NVDAx
reason: short explanation
"""

    def _call() -> dict[str, Any] | None:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300,
        )
        content = response.choices[0].message.content or ""
        return _parse_vote_content(content, model)

    return await asyncio.to_thread(_call)


async def analyze_transcript(transcript_chunk: str, current_prices: dict[str, float]) -> dict[str, Any]:
    client = _client()
    if client is None:
        return _fallback_analysis(transcript_chunk, current_prices)

    tasks = [_model_vote(client, model, transcript_chunk, current_prices) for model in configured_models()]
    raw_votes = await asyncio.gather(*tasks, return_exceptions=True)
    errors = [
        f"{type(vote).__name__}: {str(vote)[:160]}"
        for vote in raw_votes
        if isinstance(vote, Exception)
    ]
    votes = [vote for vote in raw_votes if isinstance(vote, dict)]

    if not votes:
        fallback = _fallback_analysis(transcript_chunk, current_prices)
        if errors:
            fallback["reason"] = "Featherless API calls failed; demo heuristic used. " + " | ".join(errors[:2])
        else:
            fallback["reason"] = "Featherless models returned no parseable output; demo heuristic used."
        fallback["mode"] = "fallback"
        fallback["model_errors"] = errors
        return fallback

    actions = Counter(vote["action"] for vote in votes)
    final_action = actions.most_common(1)[0][0]
    avg_confidence = int(sum(vote["confidence"] for vote in votes) / len(votes))
    ticker = Counter(vote["ticker"] for vote in votes).most_common(1)[0][0]
    sentiment = Counter(vote["sentiment"] for vote in votes).most_common(1)[0][0]
    reasons = " | ".join(vote["reason"] for vote in votes[:2])

    return {
        "action": final_action,
        "sentiment": sentiment,
        "confidence": avg_confidence,
        "ticker": ticker,
        "reason": f"Ensemble vote: {reasons}",
        "votes": votes,
        "mode": "live",
        "model_errors": errors,
    }
