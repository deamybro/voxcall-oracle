from __future__ import annotations

import os
import json
import shutil
import subprocess
import tempfile
import urllib.request
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def is_paper_mode() -> bool:
    return os.getenv("PAPER_MODE", "true").lower() != "false"


def kraken_available() -> bool:
    return shutil.which("kraken") is not None


def install_kraken_cli() -> subprocess.CompletedProcess[str]:
    url = "https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh"
    with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".sh") as installer:
        with urllib.request.urlopen(url, timeout=30) as response:
            installer.write(response.read())
        installer_path = installer.name

    os.chmod(installer_path, 0o700)
    try:
        return subprocess.run(["sh", installer_path], capture_output=True, text=True, check=False)
    finally:
        try:
            os.unlink(installer_path)
        except OSError:
            pass


def execute_trade(command: Sequence[str]) -> str:
    full_command = ["kraken", *command, "-o", "json"]

    if not kraken_available():
        return (
            "Kraken CLI is not installed in this environment.\n"
            f"Would run: {' '.join(full_command)}"
        )

    result = subprocess.run(full_command, capture_output=True, text=True, check=False)
    return (result.stdout + result.stderr).strip()


def execute_xstock_order(action: str, ticker: str, amount: float, order_type: str = "market") -> str:
    action = action.lower().strip()
    if action not in {"buy", "sell"}:
        raise ValueError(f"Unsupported Kraken action: {action}")

    pair = f"{ticker.replace('/', '').strip()}/USD"
    if is_paper_mode():
        command = ["paper", action, pair, str(amount), "--type", order_type]
    else:
        command = [
            "order",
            action,
            pair,
            str(amount),
            "--type",
            order_type,
            "--asset-class",
            "tokenized_asset",
        ]

    return execute_trade(command)


def paper_status() -> dict[str, object]:
    if not kraken_available():
        return {"ok": False, "mode": "paper", "message": "Kraken CLI is not installed."}

    result = subprocess.run(["kraken", "paper", "status", "-o", "json"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {"ok": False, "mode": "paper", "message": (result.stdout + result.stderr).strip()}
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"raw": result.stdout.strip()}
    return {"ok": True, "mode": "paper", "data": payload}


def _extract_price(payload: Any) -> float | None:
    if isinstance(payload, dict):
        for key in ("last", "price", "close"):
            value = payload.get(key)
            if isinstance(value, (int, float, str)):
                try:
                    return float(value)
                except ValueError:
                    pass
        close_values = payload.get("c")
        if isinstance(close_values, list) and close_values:
            try:
                return float(close_values[0])
            except (TypeError, ValueError):
                pass
        for value in payload.values():
            price = _extract_price(value)
            if price is not None:
                return price
    if isinstance(payload, list):
        for value in payload:
            price = _extract_price(value)
            if price is not None:
                return price
    return None


def xstock_prices(tickers: Sequence[str]) -> dict[str, float]:
    if not kraken_available():
        return {}

    prices: dict[str, float] = {}
    for ticker in tickers:
        pair = f"{ticker.replace('/', '').strip()}/USD"
        try:
            result = subprocess.run(
                ["kraken", "ticker", pair, "--asset-class", "tokenized_asset", "-o", "json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            continue
        if result.returncode != 0:
            continue
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        price = _extract_price(payload)
        if price is not None:
            prices[ticker] = price
    return prices
