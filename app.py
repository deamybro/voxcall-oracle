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

from agents.ensemble import analyze_transcript
from agents.executor import execute_decision
from agents.explainer import explain_decision, format_vote_table
from agents.listener import replay_demo, start_listening, transcribe_audio_file, transcribe_uploaded_bytes
from utils.health import runtime_checks
from utils.kraken_cli import xstock_prices

ROOT = Path(__file__).parent
DEFAULT_PRICES = {"AAPLx": 142.3, "TSLAx": 248.1, "NVDAx": 924.5, "MSFTx": 421.8}


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
    st.session_state.setdefault("pnl", [0, 120, 450, 320, 680])
    st.session_state.setdefault("listener_queue", queue.Queue())
    st.session_state.setdefault("listening", False)
    st.session_state.setdefault("listener_started", False)
    st.session_state.setdefault("last_spoken", "")
    st.session_state.setdefault("last_upload_error", "")


def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return loop.run_until_complete(coro)


def render_pnl() -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(y=st.session_state.pnl, mode="lines+markers", name="Paper PnL"))
    fig.update_layout(
        title="Real-time xStock PnL (Paper Mode)",
        xaxis_title="Signal",
        yaxis_title="USD",
        height=320,
        margin=dict(l=20, r=20, t=48, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_transcript(transcript: str) -> None:
    if not transcript.strip():
        st.info("Start listening, replay the demo call, or paste an earnings-call excerpt.")
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


async def process_chunk(text: str, auto_execute: bool, min_confidence: int) -> dict[str, Any]:
    st.session_state.transcript += text.strip() + "\n"
    live_prices = await asyncio.to_thread(xstock_prices, DEFAULT_PRICES.keys())
    prices = {**DEFAULT_PRICES, **live_prices}
    decision = await analyze_transcript(text, prices)
    decision["timestamp"] = datetime.now(UTC).isoformat(timespec="seconds")
    st.session_state.decisions.insert(0, decision)

    if auto_execute and decision.get("confidence", 0) >= min_confidence:
        result = execute_decision(decision, min_confidence=min_confidence)
        st.session_state.executions.insert(0, result)
        delta = 180 if decision.get("action") == "buy" else -120 if decision.get("action") == "sell" else 0
        st.session_state.pnl.append(st.session_state.pnl[-1] + delta)

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


def render_decision(decision: dict[str, Any] | None, voice_readout: bool) -> None:
    if not decision:
        st.info("Awaiting transcript signal.")
        return

    cols = st.columns(4)
    cols[0].metric("Action", str(decision.get("action", "hold")).upper())
    cols[1].metric("Ticker", decision.get("ticker", "AAPLx"))
    cols[2].metric("Confidence", f"{decision.get('confidence', 0)}%")
    cols[3].metric("Mode", decision.get("mode", "live").upper())
    st.success(explain_decision(decision))
    if voice_readout:
        speak_decision(decision)

    vote_rows = format_vote_table(decision)
    if vote_rows:
        st.dataframe(pd.DataFrame(vote_rows), use_container_width=True, hide_index=True)


def main() -> None:
    st.set_page_config(page_title="VoxCall Oracle", layout="wide")
    load_css()
    init_state()

    st.title("VoxCall Oracle")
    st.caption("Live earnings calls to xStock decisions with Speechmatics, Featherless, Kraken CLI, Vultr, and Coolify.")

    with st.sidebar:
        st.header("Controls")
        auto_execute = st.toggle("Auto execute paper trades", value=True)
        voice_readout = st.toggle("Voice readout", value=True)
        min_confidence = st.slider("Trade confidence threshold", 50, 95, DEFAULT_MIN_CONFIDENCE, 5)
        st.divider()
        if st.button("Start live listening", use_container_width=True):
            start_listener_thread()
            st.rerun()

        if st.session_state.listening:
            st.caption("Listening is active. The dashboard refreshes as chunks arrive.")

        if st.button("Replay demo call", use_container_width=True):
            async def _collect(chunk: str) -> None:
                await process_chunk(chunk, auto_execute, min_confidence)

            run_async(replay_demo(_collect, delay=0))
            st.rerun()

        if st.button("Clear session", use_container_width=True):
            for key in ["transcript", "decisions", "executions", "pnl"]:
                st.session_state.pop(key, None)
            st.rerun()

        st.divider()
        st.subheader("Deployment")
        for check in runtime_checks():
            st.caption(f"{'OK' if check.ok else 'WARN'} {check.name}: {check.detail}")

    drained = drain_listener_queue(auto_execute, min_confidence)
    if drained:
        st.rerun()

    left, right = st.columns([1.15, 0.85])

    with left:
        st.subheader("Live Transcript")
        render_transcript(st.session_state.transcript)

        sample = st.text_area(
            "Add earnings-call excerpt",
            value="[CEO] Nvidia beat expectations, raised guidance, and reported strong demand across enterprise AI customers.",
            height=110,
        )
        if st.button("Analyze excerpt", type="primary"):
            run_async(process_chunk(sample, auto_execute, min_confidence))
            st.rerun()

        uploaded_audio = st.file_uploader(
            "Upload earnings-call audio",
            type=["wav", "mp3", "m4a", "mp4", "webm"],
            key="earnings_audio_upload",
        )
        st.caption("Use the bundled test audio if the file picker does not refresh.")

        upload_col, demo_audio_col = st.columns(2)
        with upload_col:
            transcribe_upload = st.button(
                "Transcribe uploaded audio",
                disabled=uploaded_audio is None,
                use_container_width=True,
            )
        with demo_audio_col:
            demo_audio_path = ROOT / "demo" / "speechmatics_test_call.wav"
            transcribe_demo_audio = st.button(
                "Transcribe bundled demo audio",
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
        st.subheader("Ensemble Decision")
        latest = st.session_state.decisions[0] if st.session_state.decisions else None
        render_decision(latest, voice_readout)

    st.subheader("Paper PnL")
    render_pnl()

    if st.session_state.executions:
        st.subheader("Kraken CLI Output")
        st.code("\n\n".join(st.session_state.executions[:3]), language="text")

    if st.session_state.decisions:
        st.subheader("Decision Log")
        rows = [
            {
                "time": item.get("timestamp", ""),
                "ticker": item.get("ticker", ""),
                "action": item.get("action", ""),
                "confidence": item.get("confidence", 0),
                "sentiment": item.get("sentiment", ""),
                "reason": item.get("reason", ""),
            }
            for item in st.session_state.decisions
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if st.session_state.listening:
        time.sleep(1)
        st.rerun()


if __name__ == "__main__":
    main()
