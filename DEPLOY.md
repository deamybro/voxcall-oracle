# Deployment — Streamlit Community Cloud

## Free Deployment (Recommended)

1. Push the repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**.
4. Select your repository, branch `main`, and main file `app.py`.
5. Click **Advanced settings** and add your secrets as TOML:

```toml
SPEECHMATICS_API_KEY = "your_speechmatics_key"
FEATHERLESS_API_KEY = "your_featherless_key"
KRAKEN_API_KEY = "your_kraken_key"
KRAKEN_API_SECRET = "your_kraken_secret"
PAPER_MODE = "true"
FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"
FEATHERLESS_MODELS = "DragonLLM/Llama-Open-Finance-8B,AdaptLLM/finance-chat,TheFinAI/Fin-o1-8B"
TRADE_AMOUNT = "0.05"
MIN_TRADE_CONFIDENCE = "75"
```

6. Click **Deploy**. The app will be live at `https://your-app.streamlit.app`.

## How It Works

- `packages.txt` tells Streamlit Cloud to install system packages (`portaudio19-dev`, `build-essential`, `curl`) before pip.
- `requirements.txt` installs all Python dependencies.
- `.streamlit/config.toml` configures the dark theme and server settings.
- Secrets are injected as environment variables, accessible via `os.getenv()` and `st.secrets`.

## Production Notes

- Browser visitors cannot expose their local microphone directly to a remote Streamlit server. Use the **uploaded-audio Speechmatics path** for cloud judging — upload a `.wav` or `.mp3` of an earnings call and the app transcribes it via Speechmatics batch diarization.
- For a **local laptop demo** where the server has microphone access, use **Start live listening**.
- Kraken CLI may not be available on Streamlit Cloud. The app gracefully degrades — it shows the command that *would* be executed. For full Kraken CLI validation, use Docker locally or on a Linux server.
- Kraken paper mode uses `kraken paper buy/sell` and does not require API credentials.
- Live xStock mode uses `kraken order buy/sell ... --asset-class tokenized_asset` and requires a properly permissioned Kraken account.

## Docker Alternative

If you prefer Docker:

```bash
docker compose up --build
```

Or build directly:

```bash
docker build -t voxcall-oracle .
docker run -p 8501:8501 --env-file .env voxcall-oracle
```

## Demo Video Beat Sheet

0-15s: Title and one-line pitch.

15-45s: Real-time transcript or pasted earnings-call excerpt with speaker labels.

45-90s: Finance ensemble decision and confidence.

90-120s: Paper Kraken order command and output.

120-150s: Streamlit dashboard and PnL chart.

Final: Mention open source, Streamlit Cloud deployment, Speechmatics, Featherless, and Kraken CLI.
