# VoxCall Oracle Submission Kit

## Short Description

VoxCall Oracle is a real-time voice-first trading agent that listens to earnings calls, detects speaker-aware financial signals, runs a Featherless finance model ensemble, and routes high-confidence xStock trades through Kraken CLI in paper mode.

## Long Description

VoxCall Oracle turns live earnings-call audio into an enterprise-grade trading workflow. Speechmatics handles real-time transcription and speaker diarization, so management, analysts, and operators are separated in the transcript. Each transcript chunk is sent to a three-model Featherless finance ensemble that votes on sentiment, confidence, ticker, action, and rationale. When confidence crosses the configured threshold, the executor prepares a Kraken CLI xStock order with `PAPER_MODE=true` by default.

The Streamlit dashboard is designed for a live hackathon demo: speaker-colored transcript rows, ensemble decision cards, model vote logs, browser voice readouts, Kraken CLI output, and a paper PnL chart. The app is Docker-ready and deployable on Vultr through Coolify.

## Tags

Speechmatics, Kraken, Featherless, Vultr, Coolify, Streamlit, LangGraph, xStocks, Trading Agent, Voice AI, Enterprise AI, Multimodal Intelligence, Agentic Workflow, Python

## Demo Video Script

0-15s: "This is VoxCall Oracle: live earnings calls to xStock trading decisions."

15-45s: Start the demo replay or live listener. Show speaker diarization in the transcript panel.

45-75s: Show the Featherless ensemble decision: action, confidence, ticker, and model votes.

75-105s: Trigger a high-confidence NVDAx/AAPLx paper trade and show the Kraken CLI output.

105-135s: Show the paper PnL chart and decision log updating.

135-150s: Close with deployment: open-source, MIT licensed, deployed on Vultr with Coolify, built for Speechmatics, Kraken, Featherless, and Vultr prizes.

## Social Posts

Day 1:
Building VoxCall Oracle for #AIAgentOlympics: live earnings calls to xStock paper trades with Speechmatics, Featherless, Kraken CLI, and Vultr. @krakenfx @lablabai @Surgexyz_

Day 2:
Real-time speaker diarization is live: CEO, CFO, and analyst remarks become structured trading signals inside VoxCall Oracle. @krakenfx @lablabai @Surgexyz_

Day 3:
The Featherless finance ensemble is voting across sentiment, confidence, action, ticker, and rationale. High-confidence signals route to Kraken CLI paper trades. @krakenfx @lablabai @Surgexyz_

Day 4:
First VoxCall Oracle paper execution demo: earnings-call signal to xStock order command, with PnL tracking in Streamlit. @krakenfx @lablabai @Surgexyz_

Day 5:
VoxCall Oracle is deployable on Vultr with Coolify: Streamlit dashboard, Speechmatics listener, Featherless ensemble, Kraken CLI execution. @krakenfx @lablabai @Surgexyz_
