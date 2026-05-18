from __future__ import annotations

import asyncio
import html
import json
import os
import queue
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objs as go
import streamlit as st
import streamlit.components.v1 as components

# Force Streamlit Cloud secrets into environment variables for API clients
try:
    for k, v in st.secrets.items():
        if isinstance(v, str):
            os.environ[k] = v
except Exception:
    pass

from agents.ensemble import analyze_transcript
from agents.executor import execute_decision
from agents.explainer import explain_decision, format_vote_table
from agents.listener import replay_demo, start_listening, transcribe_audio_file, transcribe_uploaded_bytes
from utils.health import runtime_checks
from utils.kraken_cli import xstock_prices

ROOT = Path(__file__).parent
DEFAULT_PRICES = {"AAPLx": 142.3, "TSLAx": 248.1, "NVDAx": 924.5, "MSFTx": 421.8}

SPONSORS = [
    ("🎙️", "Speechmatics"),
    ("🪶", "Featherless"),
    ("🐙", "Kraken"),
    ("☁️", "Vultr"),
    ("🧊", "Coolify"),
    ("🔗", "LangGraph"),
]


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


DEFAULT_MIN_CONFIDENCE = max(50, min(env_int("MIN_TRADE_CONFIDENCE", 75), 95))


def load_css() -> None:
    css_path = ROOT / "static" / "styles.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def init_state() -> None:
    st.session_state.setdefault("transcript", "")
    st.session_state.setdefault("decisions", [])
    st.session_state.setdefault("executions", [])
    st.session_state.setdefault("pnl", [0])
    st.session_state.setdefault("pnl_timestamps", [datetime.now(UTC).isoformat(timespec="seconds")])
    st.session_state.setdefault("listener_queue", queue.Queue())
    st.session_state.setdefault("listening", False)
    st.session_state.setdefault("listener_started", False)
    st.session_state.setdefault("last_spoken", "")
    st.session_state.setdefault("last_upload_error", "")
    st.session_state.setdefault("live_prices", {})


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


# ── Rendering helpers ──────────────────────────────────────────

def render_hero() -> None:
    listening = st.session_state.listening
    status_html = (
        "<span class='live-dot'></span> LIVE"
        if listening
        else "⏸ STANDBY"
    )
    st.markdown(
        f"""
        <div class='hero-bar'>
            <span class='logo'>VoxCall Oracle</span>
            <span class='tagline'>{status_html} &nbsp;·&nbsp; Live Earnings → xStock Decisions</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sponsor_badges() -> None:
    badges = "".join(
        f"<span class='sponsor-badge'>{icon} {name}</span>"
        for icon, name in SPONSORS
    )
    st.markdown(f"<div class='sponsor-row'>{badges}</div>", unsafe_allow_html=True)


def render_price_ticker() -> None:
    prices = {**DEFAULT_PRICES, **st.session_state.live_prices}
    items = "".join(
        f"<span class='price-item'>"
        f"<span class='price-symbol'>{ticker}</span>"
        f"<span class='price-value'>${price:,.2f}</span>"
        f"</span>"
        for ticker, price in prices.items()
    )
    st.markdown(f"<div class='price-ticker'>{items}</div>", unsafe_allow_html=True)


def render_pnl() -> None:
    pnl_data = st.session_state.pnl
    timestamps = st.session_state.pnl_timestamps

    colors = ["#34d399" if v >= 0 else "#f87171" for v in pnl_data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(pnl_data))),
        y=pnl_data,
        mode="lines+markers",
        name="Paper PnL",
        line=dict(color="#2dd4bf", width=2.5),
        marker=dict(size=6, color=colors, line=dict(width=1, color="#0a0e17")),
        fill="tozeroy",
        fillcolor="rgba(45, 212, 191, 0.08)",
    ))
    fig.update_layout(
        title=None,
        xaxis_title="Signal #",
        yaxis_title="USD",
        height=300,
        margin=dict(l=20, r=20, t=16, b=36),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#94a3b8"),
        xaxis=dict(gridcolor="rgba(148,163,184,0.08)", zeroline=False),
        yaxis=dict(gridcolor="rgba(148,163,184,0.08)", zeroline=True, zerolinecolor="rgba(148,163,184,0.15)"),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_transcript(transcript: str) -> None:
    if not transcript.strip():
        st.info("Start listening, replay a call, upload audio, or paste an earnings-call excerpt.")
        return

    rows = []
    for line in transcript.strip().splitlines():
        match = re.match(r"^\[(?P<speaker>[^\]]+)\]\s*(?P<text>.*)$", line.strip())
        speaker = match.group("speaker") if match else "speaker"
        text = match.group("text") if match else line
        speaker_class = re.sub(r"[^a-z0-9-]", "-", speaker.lower())
        rows.append(
            "<div class='transcript-row'>"
            f"<span class='speaker-pill speaker-{speaker_class}'>{html.escape(speaker)}</span>"
            f"<span class='transcript-text'>{html.escape(text)}</span>"
            "</div>"
        )

    st.markdown(f"<div class='transcript-panel'>{''.join(rows)}</div>", unsafe_allow_html=True)


def speak_decision(decision: dict[str, Any]) -> None:
    timestamp = str(decision.get("timestamp", ""))
    if not timestamp or st.session_state.last_spoken == timestamp:
        return

    text = explain_decision(decision)
    safe_text = json.dumps(text)
    components.html(
        f"""
        <script>
        const text = {safe_text};
        if ("speechSynthesis" in window) {{
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.rate = 0.96;
          utterance.pitch = 1.0;
          window.speechSynthesis.speak(utterance);
        }}
        </script>
        """,
        height=0,
    )
    st.session_state.last_spoken = timestamp


def render_decision_card(decision: dict[str, Any] | None, voice_readout: bool) -> None:
    if not decision:
        st.info("Awaiting transcript signal — paste text, upload audio, or start the live listener.")
        return

    action = str(decision.get("action", "hold")).lower()
    confidence = int(decision.get("confidence", 0))
    ticker = decision.get("ticker", "AAPLx")
    sentiment = decision.get("sentiment", "neutral")
    mode = decision.get("mode", "live")
    reason = decision.get("reason", "")

    # Confidence bar class
    if confidence >= 75:
        conf_class = "confidence-high"
    elif confidence >= 50:
        conf_class = "confidence-mid"
    else:
        conf_class = "confidence-low"

    st.markdown(
        f"""
        <div class='decision-card action-{action}'>
            <div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:0.75rem;'>
                <span class='action-badge action-{action}'>{action.upper()}</span>
                <span style='font-size:0.75rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;'>
                    {'🔴 LIVE' if mode == 'live' else '🟡 PAPER' if 'paper' in mode or 'demo' in mode or 'fallback' in mode else mode.upper()}
                </span>
            </div>
            <div style='display:grid;grid-template-columns:1fr 1fr;gap:0.5rem;margin-bottom:0.75rem;'>
                <div>
                    <div style='font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;'>Ticker</div>
                    <div style='font-size:1.3rem;font-weight:800;font-family:JetBrains Mono,monospace;color:var(--accent);'>{ticker}</div>
                </div>
                <div>
                    <div style='font-size:0.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;'>Confidence</div>
                    <div style='font-size:1.3rem;font-weight:800;font-family:JetBrains Mono,monospace;'>{confidence}%</div>
                </div>
            </div>
            <div class='confidence-bar-track'>
                <div class='confidence-bar-fill {conf_class}' style='width:{confidence}%;'></div>
            </div>
            <div style='margin-top:0.75rem;font-size:0.82rem;color:var(--text-secondary);line-height:1.55;'>
                <strong style='color:var(--text-primary);'>{sentiment.capitalize()}</strong> — {html.escape(reason[:300])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if voice_readout:
        speak_decision(decision)

    vote_rows = format_vote_table(decision)
    if vote_rows:
        st.markdown("**Model Votes**")
        st.dataframe(pd.DataFrame(vote_rows), use_container_width=True, hide_index=True)


def render_architecture() -> None:
    st.markdown(
        """
        <div class='arch-flow'>
            <span class='arch-node highlight'>🎙️ Speechmatics<br><small>RT + Diarization</small></span>
            <span class='arch-arrow'>→</span>
            <span class='arch-node'>📝 Transcript<br><small>Speaker-labeled</small></span>
            <span class='arch-arrow'>→</span>
            <span class='arch-node highlight'>🪶 Featherless<br><small>3-Model Ensemble</small></span>
            <span class='arch-arrow'>→</span>
            <span class='arch-node'>⚖️ Risk Gate<br><small>Confidence Check</small></span>
            <span class='arch-arrow'>→</span>
            <span class='arch-node highlight'>🐙 Kraken CLI<br><small>xStock Order</small></span>
            <span class='arch-arrow'>→</span>
            <span class='arch-node'>📊 PnL Tracker<br><small>Paper / Live</small></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_health_sidebar() -> None:
    st.subheader("System Status")
    for check in runtime_checks():
        css = "health-ok" if check.ok else "health-warn"
        icon = "●" if check.ok else "◌"
        st.markdown(
            f"<div class='health-badge {css}'>{icon} {check.name}: {check.detail}</div>",
            unsafe_allow_html=True,
        )


# ── Processing pipeline ───────────────────────────────────────

async def process_chunk(text: str, auto_execute: bool, min_confidence: int) -> dict[str, Any]:
    st.session_state.transcript += text.strip() + "\n"

    # Fetch live prices
    live_prices = await asyncio.to_thread(xstock_prices, DEFAULT_PRICES.keys())
    st.session_state.live_prices = live_prices
    prices = {**DEFAULT_PRICES, **live_prices}

    decision = await analyze_transcript(text, prices)
    decision["timestamp"] = datetime.now(UTC).isoformat(timespec="seconds")
    st.session_state.decisions.insert(0, decision)

    if auto_execute and decision.get("confidence", 0) >= min_confidence and decision.get("action") in {"buy", "sell"}:
        result = execute_decision(decision, min_confidence=min_confidence)
        st.session_state.executions.insert(0, result)
        delta = 180 if decision.get("action") == "buy" else -120
        st.session_state.pnl.append(st.session_state.pnl[-1] + delta)
    else:
        st.session_state.pnl.append(st.session_state.pnl[-1])

    st.session_state.pnl_timestamps.append(datetime.now(UTC).isoformat(timespec="seconds"))
    return decision


def start_listener_thread() -> None:
    if st.session_state.listener_started:
        return

    transcript_queue = st.session_state.listener_queue

    async def _callback(chunk: str) -> None:
        transcript_queue.put(chunk)

    def _runner() -> None:
        try:
            asyncio.run(start_listening(_callback))
        except Exception as exc:
            transcript_queue.put(f"[system] Listener stopped: {exc}")
        finally:
            transcript_queue.put(None)

    thread = threading.Thread(target=_runner, name="speechmatics-listener", daemon=True)
    thread.start()
    st.session_state.listener_started = True
    st.session_state.listening = True


def drain_listener_queue(auto_execute: bool, min_confidence: int) -> int:
    drained = 0
    transcript_queue = st.session_state.listener_queue
    while not transcript_queue.empty():
        chunk = transcript_queue.get_nowait()
        if chunk is None:
            st.session_state.listening = False
            st.session_state.listener_started = False
            continue
        run_async(process_chunk(chunk, auto_execute, min_confidence))
        drained += 1
    return drained


# ── Main application ──────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="VoxCall Oracle",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_css()
    init_state()

    # ── Sidebar ────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Controls")
        auto_execute = st.toggle("Auto execute trades", value=True)
        voice_readout = st.toggle("Voice readout", value=True)
        min_confidence = st.slider("Confidence threshold", 50, 95, DEFAULT_MIN_CONFIDENCE, 5)

        st.divider()

        if st.button("🎙️ Start live listening", use_container_width=True, type="primary" if not st.session_state.listening else "secondary"):
            start_listener_thread()
            st.rerun()

        if st.session_state.listening:
            st.markdown("<div class='health-badge health-ok'><span class='live-dot'></span> Listener active</div>", unsafe_allow_html=True)

        if st.button("▶️ Replay demo call", use_container_width=True):
            async def _collect(chunk: str) -> None:
                await process_chunk(chunk, auto_execute, min_confidence)
            run_async(replay_demo(_collect, delay=0))
            st.rerun()

        if st.button("🗑️ Clear session", use_container_width=True):
            for key in ["transcript", "decisions", "executions", "pnl", "pnl_timestamps", "live_prices"]:
                st.session_state.pop(key, None)
            st.rerun()

        st.divider()
        render_health_sidebar()

    # ── Drain live listener ────────────────────────────────
    drained = drain_listener_queue(auto_execute, min_confidence)
    if drained:
        st.rerun()

    # ── Hero + sponsors + prices ───────────────────────────
    render_hero()
    render_sponsor_badges()
    render_price_ticker()

    # ── Main columns ───────────────────────────────────────
    left, right = st.columns([1.15, 0.85])

    with left:
        st.markdown("#### 📝 Live Transcript")
        render_transcript(st.session_state.transcript)

        sample = st.text_area(
            "Earnings-call excerpt",
            value="[CEO] Nvidia beat expectations, raised guidance, and reported strong demand across enterprise AI customers.",
            height=100,
        )
        if st.button("⚡ Analyze excerpt", type="primary"):
            run_async(process_chunk(sample, auto_execute, min_confidence))
            st.rerun()

        uploaded_audio = st.file_uploader(
            "Upload earnings-call audio",
            type=["wav", "mp3", "m4a", "mp4", "webm"],
            key="earnings_audio_upload",
        )

        upload_col, demo_audio_col = st.columns(2)
        with upload_col:
            transcribe_upload = st.button(
                "Transcribe upload",
                disabled=uploaded_audio is None,
                use_container_width=True,
            )
        with demo_audio_col:
            demo_audio_path = ROOT / "demo" / "speechmatics_test_call.wav"
            transcribe_demo_audio = st.button(
                "Transcribe bundled audio",
                disabled=not demo_audio_path.exists(),
                use_container_width=True,
            )

        if transcribe_upload or transcribe_demo_audio:
            try:
                with st.spinner("Transcribing with Speechmatics diarization..."):
                    if transcribe_upload:
                        chunks = run_async(transcribe_uploaded_bytes(uploaded_audio.name, uploaded_audio.getvalue()))
                    else:
                        chunks = run_async(transcribe_audio_file(demo_audio_path))
                    if not chunks:
                        st.warning("Speechmatics returned no transcript chunks for this audio.")
                    for chunk in chunks:
                        run_async(process_chunk(chunk, auto_execute, min_confidence))
                st.session_state.last_upload_error = ""
                st.rerun()
            except Exception as exc:
                st.session_state.last_upload_error = f"{type(exc).__name__}: {exc}"

        if st.session_state.last_upload_error:
            st.error(st.session_state.last_upload_error)

    with right:
        st.markdown("#### 🎯 Ensemble Decision")
        latest = st.session_state.decisions[0] if st.session_state.decisions else None
        render_decision_card(latest, voice_readout)

    # ── PnL chart ──────────────────────────────────────────
    st.markdown("#### 📊 Paper PnL Tracker")
    render_pnl()

    # ── Kraken CLI output ──────────────────────────────────
    if st.session_state.executions:
        st.markdown("#### 🐙 Kraken CLI Output")
        st.code("\n\n".join(st.session_state.executions[:5]), language="text")

    # ── Decision log ───────────────────────────────────────
    if st.session_state.decisions:
        st.markdown("#### 📋 Decision Log")
        rows = [
            {
                "time": item.get("timestamp", ""),
                "ticker": item.get("ticker", ""),
                "action": item.get("action", ""),
                "confidence": item.get("confidence", 0),
                "sentiment": item.get("sentiment", ""),
                "mode": item.get("mode", ""),
                "reason": item.get("reason", "")[:120],
            }
            for item in st.session_state.decisions
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Architecture ───────────────────────────────────────
    with st.expander("🏗️ Architecture", expanded=False):
        render_architecture()

    # ── Auto-refresh while listening ───────────────────────
    if st.session_state.listening:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
