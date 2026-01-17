# API PRD Generator

A web UI for generating API Integration PRDs using Claude AI.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Hosting Options

### Option 1: Streamlit Community Cloud (FREE - Recommended)

1. Push this folder to a GitHub repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Sign in with GitHub
4. Click "New app"
5. Select your repo, branch, and `app.py`
6. Click "Deploy"

**Note**: Users will need to enter their own Anthropic API key.

### Option 2: Railway ($5/month)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### Option 3: Render (Free tier available)

1. Create a `render.yaml` in this folder (already included)
2. Push to GitHub
3. Go to [render.com](https://render.com)
4. New > Web Service > Connect your repo
5. Render auto-detects the config

### Option 4: Docker (Self-hosted)

```bash
docker build -t prd-generator .
docker run -p 8501:8501 prd-generator
```

## Environment Variables

For production, set the API key as an environment variable instead of user input:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

Then modify `app.py` to read from environment:
```python
api_key = os.environ.get("ANTHROPIC_API_KEY") or st.text_input(...)
```

## Security Notes

- Never commit API keys to git
- For team use, consider setting a shared API key as environment variable
- Streamlit Community Cloud supports secrets management
