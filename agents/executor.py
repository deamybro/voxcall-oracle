from __future__ import annotations

import os
from typing import Any

from utils.kraken_cli import execute_xstock_order, is_paper_mode


def execute_decision(decision: dict[str, Any], amount: float | None = None, min_confidence: int = 70) -> str:
    action = str(decision.get("action", "hold")).lower()
    confidence = int(decision.get("confidence", 0))
    trade_amount = amount if amount is not None else float(os.getenv("TRADE_AMOUNT", "0.05"))

    if confidence < min_confidence or action == "hold":
        return f"No trade - action={action}, confidence={confidence}, threshold={min_confidence}."

    if action not in {"buy", "sell"}:
        return f"No trade - unsupported action: {action}."

    ticker = str(decision.get("ticker", "AAPLx")).replace("/", "").strip() or "AAPLx"
    result = execute_xstock_order(action, ticker, trade_amount)
    mode = "PAPER" if is_paper_mode() else "LIVE"
    return f"{mode} EXECUTED: {action} {ticker}/USD {trade_amount}\n{result}"
