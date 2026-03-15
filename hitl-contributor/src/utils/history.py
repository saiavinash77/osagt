"""
Run history — persists every agent run to a local JSON file.
Useful for avoiding re-attempting the same issue and for auditing submissions.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

HISTORY_FILE = Path("logs/run_history.json")


def _load() -> List[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not read history file: {e}")
        return []


def _save(records: List[dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(records, indent=2, default=str),
        encoding="utf-8",
    )


def record_run(
    repo_full_name: str,
    issue_number: int,
    issue_title: str,
    outcome: str,           # "approved", "rejected", "error", "feedback_limit"
    pr_url: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Append a run record to the history file."""
    records = _load()
    records.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo": repo_full_name,
        "issue_number": issue_number,
        "issue_title": issue_title,
        "outcome": outcome,
        "pr_url": pr_url,
        "error": error,
    })
    _save(records)
    logger.info(f"Run recorded: {repo_full_name}#{issue_number} → {outcome}")


def was_already_attempted(repo_full_name: str, issue_number: int) -> bool:
    """Return True if this issue has been attempted before (any outcome)."""
    records = _load()
    for r in records:
        if r.get("repo") == repo_full_name and r.get("issue_number") == issue_number:
            return True
    return False


def get_recent_prs(limit: int = 10) -> List[dict]:
    """Return the last `limit` runs that resulted in a PR."""
    records = _load()
    prs = [r for r in records if r.get("outcome") == "approved" and r.get("pr_url")]
    return prs[-limit:]


def print_history_table() -> None:
    """Pretty-print run history to the console using Rich."""
    from rich.console import Console
    from rich.table import Table

    records = _load()
    console = Console()

    if not records:
        console.print("[yellow]No run history found.[/]")
        return

    table = Table(title="📋 Run History", show_lines=True)
    table.add_column("Timestamp", style="dim", width=22)
    table.add_column("Repo / Issue", style="cyan")
    table.add_column("Outcome", style="bold")
    table.add_column("PR URL")

    outcome_colors = {
        "approved": "green",
        "rejected": "red",
        "error": "red",
        "feedback_limit": "yellow",
    }

    for r in reversed(records[-20:]):    # show last 20
        ts = r.get("timestamp", "")[:19].replace("T", " ")
        repo_issue = f"{r.get('repo')} #{r.get('issue_number')}\n{r.get('issue_title', '')[:40]}"
        outcome = r.get("outcome", "unknown")
        color = outcome_colors.get(outcome, "white")
        pr_url = r.get("pr_url") or "—"
        table.add_row(ts, repo_issue, f"[{color}]{outcome}[/]", pr_url)

    console.print(table)
