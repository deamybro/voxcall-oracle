# VoxCall Oracle — Voice-Powered Earnings Call Trading Agent

> **Live production agent** that listens to earnings calls in real-time, analyzes xStock impact with a Featherless finance ensemble, and executes trades via Kraken CLI.

Deployed on **Streamlit Community Cloud** — free, live, open-source.

---

## Architecture

```
┌──────────────┐     ┌────────────────┐     ┌──────────────────┐
│  🎙️ Audio     │────▶│  Speechmatics   │────▶│  Speaker-labeled  │
│  Input       │     │  RT + Batch     │     │  Transcript       │
└──────────────┘     │  Diarization    │     └────────┬─────────┘
                     └────────────────┘              │
                                                     ▼
                     ┌────────────────┐     ┌──────────────────┐
                     │  🪶 Featherless  │◀────│  Ensemble Vote    │
                     │  3-Model        │     │  sentiment/action │
                     │  Finance LLMs   │     │  confidence/ticker│
                     └────────────────┘     └────────┬─────────┘
                                                     │
                                                     ▼
                     ┌────────────────┐     ┌──────────────────┐
                     │  ⚖️ Risk Gate   │────▶│  🐙 Kraken CLI    │
                     │  Confidence     │     │  xStock Order     │
                     │  Threshold      │     │  Paper / Live     │
                     └────────────────┘     └────────┬─────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │  📊 Dashboard     │
                                            │  PnL + Decisions  │
                                            │  Voice Readout    │
                                            └──────────────────┘
```

## Features

- 🎙️ **Speechmatics** — Real-time microphone transcription + batch audio upload with speaker diarization
- 🪶 **Featherless** — 3-model finance ensemble (`Llama-Open-Finance-8B`, `finance-chat`, `Fin-o1-8B`) with majority vote
- 🐙 **Kraken CLI** — xStock paper + live order execution (`kraken paper buy/sell` / `kraken order buy/sell`)
- ⚖️ **Risk Gate** — Configurable confidence threshold blocks low-signal trades
- 📊 **Live Dashboard** — Streamlit with dark theme, PnL chart, decision log, model votes, voice readout
- 🔗 **LangGraph** — Multi-agent workflow: Analyze → Risk Gate → Execute → Explain
- ☁️ **Streamlit Cloud** — Free deployment with secrets management

## Targets

Speechmatics · Kraken (PnL + Social) · Featherless · Agentic Workflows · Multimodal Intelligence · Enterprise Utility

## Quick Start

```bash
cp .env.example .env
# fill in your API keys
pip install -r requirements.txt
streamlit run app.py
```

Open `http://localhost:8501`.

## Deploy to Streamlit Community Cloud (Free)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io).
3. Click **New app** → select your repo → branch `main` → file `app.py`.
4. Under **Advanced settings** → **Secrets**, add your keys:
   ```toml
   SPEECHMATICS_API_KEY = "your_key"
   FEATHERLESS_API_KEY = "your_key"
   PAPER_MODE = "true"
   ```
5. Click **Deploy**. Your app will be live at `https://your-app.streamlit.app`.

## Docker (Optional)

```bash
docker compose up --build
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SPEECHMATICS_API_KEY` | For live audio | Speechmatics API key for RT + batch |
| `FEATHERLESS_API_KEY` | For live ensemble | Featherless API key |
| `KRAKEN_API_KEY` | For PnL audit | Kraken read-only key |
| `KRAKEN_API_SECRET` | For live trades | Kraken secret |
| `PAPER_MODE` | No (default: `true`) | Paper trading mode |
| `TRADE_AMOUNT` | No (default: `0.05`) | Order size |
| `MIN_TRADE_CONFIDENCE` | No (default: `75`) | Minimum confidence to execute |
| `FEATHERLESS_MODELS` | No | Comma-separated model IDs |
| `FEATHERLESS_BASE_URL` | No | Custom Featherless endpoint |

## Live Integrations

- **Speechmatics**: Real-time microphone path for local; batch diarization for uploaded audio in cloud.
- **Featherless**: OpenAI-compatible finance ensemble with configurable model IDs.
- **Kraken CLI**: Paper mode via `kraken paper buy/sell`. Live xStock mode via `kraken order ... --asset-class tokenized_asset`.

## Kraken Validation

After deployment, run inside the container:

```bash
sh scripts/validate_kraken.sh
```

## Submission

See [SUBMISSION.md](SUBMISSION.md) for lablab.ai copy, demo video script, tags, and social posts.

## Safety

`PAPER_MODE=true` is the default. All trades go through the **risk gate** — low-confidence signals are blocked. Switch to live execution only after reviewing your Kraken CLI authentication and risk controls.

## License

MIT. See [LICENSE](LICENSE).
