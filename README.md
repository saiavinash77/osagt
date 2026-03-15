# 🤖 HITL Open Source Contribution Agent

An AI-powered agent that finds beginner-friendly GitHub issues, drafts code fixes, and — **only after your explicit approval** — opens Pull Requests. Built with LangGraph, Claude 3.5 Sonnet (via OpenRouter), and Docker for sandboxed code execution.

> ⚠️ **Safety Disclaimer:** All contributions are manually reviewed by a human before submission. The agent cannot open a PR without your explicit approval.

---

## Architecture

```
GitHub Issues
     │
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scanner   │────▶│  Architect  │────▶│  Developer  │
│ (find issue)│     │ (make plan) │     │ (write diff)│
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                                    ┌───────────▼──────────┐
                                    │  🧑 HUMAN REVIEW      │ ◀── YOU ARE HERE
                                    │  Approve / Reject /   │
                                    │  Give Feedback        │
                                    └───────────┬──────────┘
                                                │ Approve only
                                        ┌───────▼───────┐
                                        │   Submitter   │
                                        │  (open PR)    │
                                        └───────────────┘
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Brain | Claude 3.5 Sonnet via OpenRouter |
| Orchestrator | LangGraph (state machine + HITL breakpoints) |
| Sandbox | Docker (isolated, no network) |
| GitHub API | PyGithub |
| Terminal UI | Rich |

---

## Setup

### 1. Prerequisites

- Python 3.11+
- Docker Desktop (or Docker Engine on Linux)
- Git

### 2. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/hitl-contributor
cd hitl-contributor
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:

| Variable | Where to get it |
|----------|----------------|
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `GITHUB_TOKEN` | GitHub → Settings → Developer Settings → Fine-grained PAT |
| `GITHUB_USERNAME` | Your GitHub username |

**GitHub Token scopes required (Fine-grained PAT):**
- Repository access: Public repositories (read)
- Permissions: Pull requests (write), Contents (write)

### 4. Build the Sandbox Image (optional but recommended)

```bash
docker build -t hitl-sandbox docker/
```

### 5. Run

```bash
python main.py
```

---

## Usage Flow

1. The agent searches GitHub for `good first issue` / `help wanted` issues
2. It analyses the repo and creates an implementation plan
3. It writes the code changes inside a Docker sandbox
4. **The agent pauses** and shows you the diff in your terminal
5. You choose: **Approve**, **Reject**, or **Give Feedback**
   - Feedback → agent rewrites the diff (up to 3 iterations)
   - Approve → PR is opened automatically
   - Reject → nothing is submitted

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ISSUE_LABELS` | `good first issue,help wanted` | Labels to search |
| `LANGUAGE_FILTER` | `python` | Repo languages to target |
| `MAX_ISSUES_TO_SCAN` | `5` | Issues to evaluate per run |
| `DOCKER_TIMEOUT_SECONDS` | `120` | Sandbox timeout |
| `LLM_MODEL` | `anthropic/claude-3.5-sonnet` | OpenRouter model |

---

## Security

- **Never** commit your `.env` file — it is listed in `.gitignore`
- Use a **Fine-grained PAT** scoped to public repos + PRs only
- The Docker sandbox runs with `--network none` — no outbound access
- The human review step is **mandatory** and cannot be bypassed

---

## Contributing

Contributions to improve the agent's logic are welcome! Please open an issue first to discuss changes.

---

## License

MIT
