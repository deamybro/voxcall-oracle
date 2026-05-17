# Vultr + Coolify Deployment

1. Go to Vultr Marketplace and deploy a Coolify instance.
2. In Coolify, connect your GitHub repository.
3. Choose Docker as the build method for the most reproducible deployment.
4. Set the public port to `8501`.
5. Add environment variables from `.env.example`.
6. Keep `PAPER_MODE=true` for the public demo.
7. The Dockerfile installs Kraken CLI automatically. If you deploy with Nixpacks instead of Docker, add this pre-build command:

```bash
curl --proto '=https' --tlsv1.2 -LsSf https://github.com/krakenfx/kraken-cli/releases/latest/download/kraken-cli-installer.sh | sh
```

8. Deploy and confirm the Coolify health check reaches `/_stcore/health`.
9. Open the app, check the sidebar deployment statuses, replay the demo call, then upload a real earnings-call clip with `SPEECHMATICS_API_KEY` configured.
10. Copy the public URL into `README.md` and your lablab.ai submission.

## Production Notes

- Browser visitors cannot expose their local microphone directly to a remote Streamlit server. Use the uploaded-audio Speechmatics path for cloud judging, and use `Start live listening` for a local laptop demo where the server has microphone access.
- Kraken paper mode uses `kraken paper buy/sell` and does not require API credentials.
- Live xStock mode uses `kraken order buy/sell ... --asset-class tokenized_asset` and requires a properly permissioned Kraken account. xStocks availability varies by jurisdiction.
- Kraken CLI does not support native Windows installation. Test it in WSL, Linux, or the Vultr/Coolify container.

## Kraken Validation

After deployment, open the Coolify terminal for the running container and run:

```bash
sh scripts/validate_kraken.sh
```

Expected:

- `kraken status -o json` returns a JSON status payload.
- `kraken ticker AAPLx/USD --asset-class tokenized_asset -o json` returns a ticker payload or a jurisdiction/availability error.
- `kraken paper buy AAPLx/USD 0.01 --type market -o json` returns a paper order result.

## Demo Video Beat Sheet

0-15s: title and one-line pitch.

15-45s: real-time transcript or pasted earnings-call excerpt with speaker labels.

45-90s: finance ensemble decision and confidence.

90-120s: paper Kraken order command and output.

120-150s: Streamlit dashboard and PnL chart.

Final: mention open source, Vultr deployment, Speechmatics, Featherless, and Kraken CLI.
