"""
HITL Contributor Agent — Unified CLI
=====================================
Usage:
  python cli.py run            # interactive terminal run (default)
  python cli.py serve          # start web server + UI
  python cli.py schedule       # run on a schedule (server mode)
  python cli.py history        # print run history table
  python cli.py check          # validate .env config
"""

import typer
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(
    name="hitl-contributor",
    help="🤖 Human-in-the-Loop AI agent for open source contributions.",
    add_completion=False,
)


# ── run ───────────────────────────────────────────────────────────────────────

@app.command()
def run(
    thread_id: Optional[str] = typer.Option(
        None, "--thread", "-t",
        help="Resume an existing LangGraph thread by ID.",
    ),
):
    """
    Run the agent interactively in the terminal.
    The agent scans GitHub, drafts a fix, then pauses for your review.
    """
    from src.config.settings import settings
    from src.utils.logging_setup import configure_logging
    configure_logging(settings.log_level, settings.log_file)

    import main as m
    if thread_id:
        m.THREAD_ID = thread_id
        m.CONFIG = {"configurable": {"thread_id": thread_id}}
    m.run_agent()


# ── serve ─────────────────────────────────────────────────────────────────────

@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload", help="Hot-reload (dev only)"),
):
    """
    Start the FastAPI web server.
    Review diffs and approve PRs from your browser at http://localhost:PORT
    """
    import uvicorn
    from src.config.settings import settings
    from src.utils.logging_setup import configure_logging
    configure_logging(settings.log_level, settings.log_file)

    typer.echo(f"🌐  Web UI: http://{host}:{port}")
    uvicorn.run(
        "web_server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


# ── schedule ──────────────────────────────────────────────────────────────────

@app.command()
def schedule(
    once: bool = typer.Option(False, "--once", help="Run once then exit."),
    interval: Optional[int] = typer.Option(
        None, "--interval", help="Override SCHEDULE_INTERVAL_HOURS from .env."
    ),
):
    """
    Run the agent on a recurring schedule (pairs with the web server for HITL).
    Set AUTO_RUN=true in .env, or use --once for a single manual trigger.
    """
    import scheduler as s
    from src.config.settings import settings
    from src.utils.logging_setup import configure_logging
    configure_logging(settings.log_level, settings.log_file)

    if interval:
        settings.__dict__["schedule_interval_hours"] = interval

    import sys
    # Patch sys.argv so scheduler's argparse gets the --once flag correctly
    sys.argv = ["scheduler.py"] + (["--once"] if once else [])
    s.main()


# ── history ───────────────────────────────────────────────────────────────────

@app.command()
def history():
    """Print the run history table (recent attempts and submitted PRs)."""
    from src.utils.history import print_history_table
    print_history_table()


# ── check ─────────────────────────────────────────────────────────────────────

@app.command()
def check():
    """
    Validate your .env configuration.
    Tests that API keys are present, GitHub auth works, and Docker is available.
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="⚙️  Configuration Check", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail", style="dim")

    # 1. Settings load
    try:
        from src.config.settings import settings
        table.add_row("Settings load", "[green]✅ OK[/]", f"Model: {settings.llm_model}")
    except Exception as e:
        table.add_row("Settings load", "[red]❌ FAIL[/]", str(e))
        console.print(table)
        return

    # 2. OpenRouter key present
    key_preview = settings.openrouter_api_key[:12] + "…" if settings.openrouter_api_key else "MISSING"
    ok = settings.openrouter_api_key.startswith("sk-or-")
    table.add_row(
        "OpenRouter API key",
        "[green]✅ OK[/]" if ok else "[red]❌ FAIL[/]",
        key_preview,
    )

    # 3. GitHub token present
    gh_preview = settings.github_token[:16] + "…" if settings.github_token else "MISSING"
    gh_ok = len(settings.github_token) > 20
    table.add_row(
        "GitHub token",
        "[green]✅ OK[/]" if gh_ok else "[red]❌ FAIL[/]",
        gh_preview,
    )

    # 4. GitHub API reachable
    try:
        from src.github.client import get_github_client
        g = get_github_client()
        user = g.get_user()
        table.add_row("GitHub auth", "[green]✅ OK[/]", f"Logged in as: {user.login}")
    except Exception as e:
        table.add_row("GitHub auth", "[red]❌ FAIL[/]", str(e))

    # 5. Docker available
    try:
        import subprocess
        result = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            table.add_row("Docker", "[green]✅ OK[/]", f"Server v{result.stdout.strip()}")
        else:
            table.add_row("Docker", "[yellow]⚠ WARNING[/]", "Docker not running (sandbox disabled)")
    except FileNotFoundError:
        table.add_row("Docker", "[yellow]⚠ WARNING[/]", "Docker not installed (sandbox disabled)")
    except Exception as e:
        table.add_row("Docker", "[yellow]⚠ WARNING[/]", str(e))

    # 6. Logs directory writable
    import os
    from pathlib import Path
    log_dir = Path(settings.log_file).parent
    writable = os.access(log_dir, os.W_OK) if log_dir.exists() else False
    table.add_row(
        "Logs directory",
        "[green]✅ OK[/]" if writable else "[yellow]⚠ Creating[/]",
        str(log_dir.resolve()),
    )
    if not writable:
        log_dir.mkdir(parents=True, exist_ok=True)

    console.print(table)


if __name__ == "__main__":
    app()
