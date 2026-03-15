# 🚀 Quick Setup Guide

Follow these steps to get the agent running in under 10 minutes.

---

## Step 1 — Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/hitl-contributor.git
cd hitl-contributor
```

---

## Step 2 — Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Step 3 — Set up credentials

```bash
cp .env.example .env
```

Open `.env` and fill in:

### OpenRouter API Key
1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Click **Create Key**
3. Copy the key starting with `sk-or-v1-…`
4. Paste into `OPENROUTER_API_KEY=` in `.env`

### GitHub Personal Access Token
1. Go to **GitHub → Settings → Developer Settings → Personal access tokens → Fine-grained tokens**
2. Click **Generate new token**
3. Set:
   - **Token name**: `hitl-contributor`
   - **Expiration**: 90 days
   - **Repository access**: Public repositories
   - **Permissions**:
     - Contents: **Read and write**
     - Pull requests: **Read and write**
4. Click **Generate token**
5. Copy and paste into `GITHUB_TOKEN=` in `.env`
6. Set `GITHUB_USERNAME=` to your GitHub username

---

## Step 4 — Validate your config

```bash
python cli.py check
```

All checks should show ✅. Docker showing ⚠ is OK — sandbox will be skipped.

---

## Step 5 — Run!

### Option A: Terminal (interactive)
```bash
python cli.py run
```
The agent will scan GitHub, generate a diff, then pause and ask for your approval.

### Option B: Web UI
```bash
python cli.py serve
```
Open **http://localhost:8000** in your browser. Click **Start New Run** and review diffs visually.

### Option C: Docker Compose (full stack)
```bash
docker-compose up --build
```
Runs both the web server and background scheduler together.

---

## Step 6 — Review & Approve

When the agent pauses at the HITL step:

- **Terminal**: Choose `a` (approve), `r` (reject), or `f` (feedback)
- **Web UI**: Click the green/red/yellow buttons

Only after you click **Approve** will a PR be submitted.

---

## Customisation

Edit `.env` to change which issues the agent targets:

```env
ISSUE_LABELS=good first issue,help wanted,beginner friendly
LANGUAGE_FILTER=python,typescript,go
MAX_ISSUES_TO_SCAN=10
```

---

## View history

```bash
python cli.py history
```

---

## Deploy to the cloud (free)

| Platform | Command |
|----------|---------|
| Northflank | Upload `northflank.json`, set env vars in dashboard |
| Render | `git push` — `render.yaml` is auto-detected |
| Railway | `railway up` — `railway.toml` is auto-detected |

Set all env vars (`OPENROUTER_API_KEY`, `GITHUB_TOKEN`, `GITHUB_USERNAME`) in the platform's secret manager — never in code.
