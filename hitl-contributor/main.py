"""
HITL Open Source Contribution Agent
Entry point — run with: python main.py
"""

import logging
import os
import sys
from dotenv import load_dotenv
from rich.console import Console
from rich import print as rprint

# Load .env before any module-level imports that read env vars
load_dotenv()

from src.agent.graph import graph
from src.agent.state import AgentState, HumanDecision
from src.ui.terminal import collect_human_decision
from src.utils.email_sender import send_notification

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Run config
# ---------------------------------------------------------------------------
THREAD_ID = "hitl-agent-run-001"   # unique ID per LangGraph memory thread
CONFIG = {"configurable": {"thread_id": THREAD_ID}}


def run_agent() -> None:
    console.rule("[bold cyan]🤖 HITL Open Source Contribution Agent[/]")
    console.print()

    initial_state = AgentState()

    # ------------------------------------------------------------------ #
    # Phase 1: Run scanner → architect → developer (auto, no human yet)   #
    # The graph will PAUSE at the 'hitl' node breakpoint automatically.   #
    # ------------------------------------------------------------------ #
    console.print("[bold]Phase 1:[/] Scanning GitHub, planning, and generating diff...\n")

    for event in graph.stream(initial_state.model_dump(), config=CONFIG, stream_mode="values"):
        # Each event is the full state after a node completes
        current_node = event.get("current_node", "")
        if current_node:
            console.print(f"  ⟶  Node completed: [bold cyan]{current_node}[/]")

    # ------------------------------------------------------------------ #
    # Phase 2: Human review (HITL breakpoint)                             #
    # ------------------------------------------------------------------ #
    current_state_snapshot = graph.get_state(config=CONFIG)
    current_state = AgentState(**current_state_snapshot.values)

    if current_state.error_message:
        console.print(f"\n[bold red]❌ Agent error:[/] {current_state.error_message}")
        sys.exit(1)

    if current_state.diff_result is None:
        console.print("\n[bold red]❌ No diff was generated. Exiting.[/]")
        sys.exit(1)

    # Show diff and collect decision
    if current_state.selected_issue:
        send_notification(
            subject=f"Action Required: Review PR for #{current_state.selected_issue.issue_number}",
            body=f"The agent has paused and generated a diff for '{current_state.selected_issue.title}'.\n\nPlease check your terminal to approve or reject the changes."
        )
    human_decision: HumanDecision = collect_human_decision(current_state)

    # Inject human decision back into the graph state
    graph.update_state(
        config=CONFIG,
        values={"human_decision": human_decision},
    )

    # ------------------------------------------------------------------ #
    # Phase 3: Resume graph (submitter or loop back to developer)         #
    # ------------------------------------------------------------------ #
    console.print("\n[bold]Phase 3:[/] Resuming agent...\n")

    for event in graph.stream(None, config=CONFIG, stream_mode="values"):
        current_node = event.get("current_node", "")
        if current_node:
            console.print(f"  ⟶  Node completed: [bold cyan]{current_node}[/]")

    # Final state
    final_snapshot = graph.get_state(config=CONFIG)
    final_state = AgentState(**final_snapshot.values)

    console.rule()
    if final_state.pull_request:
        console.print(f"\n[bold green]🎉 PR Successfully Opened![/]")
        console.print(f"   URL:    {final_state.pull_request.url}")
        console.print(f"   Title:  {final_state.pull_request.title}")
        console.print(f"   Branch: {final_state.pull_request.branch_name}")
    elif human_decision.action == "reject":
        console.print("\n[yellow]Issue rejected. No PR submitted.[/]")
    elif final_state.error_message:
        console.print(f"\n[bold red]❌ Failed:[/] {final_state.error_message}")
    else:
        console.print("\n[yellow]Run completed (no PR submitted).[/]")


if __name__ == "__main__":
    run_agent()
