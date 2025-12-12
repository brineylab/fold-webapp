# fold-webapp

Streamlit webapp for running AlphaFold3 jobs (and structured to support additional models later).

## Run

- Existing entrypoint (kept for compatibility):

```bash
streamlit run af3_web_app.py
```

- Package entrypoint:

```bash
streamlit run src/fold_webapp/main.py
```

## Configuration

Configuration is read from environment variables prefixed with `FOLD_` (optionally via a local `.env` file).

See `.env.example` for available settings.