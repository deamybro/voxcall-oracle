# VoxCall Oracle - Voice-Powered Earnings Call Trading Agent

Real-time voice-first agent that listens to live earnings calls with Speechmatics, analyzes xStock impact with a Featherless finance ensemble, and routes paper or live orders through Kraken CLI.

Deployed on Vultr via Coolify as a production-shaped Streamlit app.

Targets: Speechmatics, Kraken PnL + Social, Featherless, Vultr, Agentic Workflows, Multimodal Intelligence, Enterprise Utility.

## Quick Start

```bash
cp .env.example .env
# fill keys
pip install -r requirements.txt
streamlit run app.py
```

Open the app at `http://localhost:8501`.

## Demo Mode

The dashboard works without API keys. Paste or type an earnings-call excerpt in the demo panel and VoxCall Oracle will produce a deterministic paper-trading decision. Add `FEATHERLESS_API_KEY` to use the live finance ensemble.

Live Speechmatics listening requires `SPEECHMATICS_API_KEY` and compatible microphone/audio streaming support in the runtime. For cloud deployments, upload an earnings-call audio clip in the dashboard to use Speechmatics batch diarization from the server.

## Real Integrations

- Speechmatics realtime microphone path for local demos.
- Speechmatics batch diarization path for uploaded audio in cloud deployments.
- Featherless OpenAI-compatible finance ensemble with configurable model IDs via `FEATHERLESS_MODELS`.
- Kraken CLI paper mode via `kraken paper buy/sell`.
- Kraken CLI live xStock mode via `kraken order buy/sell ... --asset-class tokenized_asset`.
- Streamlit health endpoint at `/_stcore/health` for Coolify.

## Current Local Status

Windows local testing supports the full dashboard, Speechmatics upload transcription, and Featherless live ensemble. Kraken CLI should be validated in WSL, Linux, or the Vultr/Coolify container because the official Kraken CLI installation path does not support native Windows.

## Vultr + Coolify Deployment

See [DEPLOY.md](DEPLOY.md).

## Submission Assets

Use [SUBMISSION.md](SUBMISSION.md) for lablab.ai copy, the 2-minute demo video script, tags, and Kraken social engagement posts.

Live Demo: [your-vultr-url-here]
GitHub: [link]
Video: [YouTube link]

## Safety

`PAPER_MODE=true` is the default. Leave paper mode enabled for demos and judging. Switch to live execution only after you have reviewed your Kraken CLI authentication, command format, and risk controls.

## License

MIT. See [LICENSE](LICENSE).
