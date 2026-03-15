"""
Terminal Human-in-the-Loop Interface
Displays the diff with syntax highlighting and collects the human's decision.
"""

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.prompt import Prompt
from rich import print as rprint
import os
import threading
import sys
import select
from src.agent.state import AgentState, HumanDecision

console = Console()


def display_issue_summary(state: AgentState) -> None:
    issue = state.selected_issue
    plan = state.implementation_plan
    if not issue or not plan:
        return

    table = Table(title="📌 Selected Issue", show_header=False, box=None)
    table.add_row("[bold cyan]Repo[/]", issue.repo_full_name)
    table.add_row("[bold cyan]Issue[/]", f"#{issue.issue_number} — {issue.title}")
    table.add_row("[bold cyan]URL[/]", issue.url)
    table.add_row("[bold cyan]Labels[/]", ", ".join(issue.labels))
    table.add_row("[bold cyan]Language[/]", issue.language or "unknown")
    console.print(table)
    console.print()

    console.print(Panel(
        plan.summary,
        title=f"🏗️  Plan (complexity: [yellow]{plan.estimated_complexity}[/])",
        border_style="blue",
    ))

    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan.steps))
    console.print(f"[bold]Steps:[/]\n{steps_text}\n")

    files_text = "\n".join(f"  • {f}" for f in plan.files_to_modify)
    console.print(f"[bold]Files to change:[/]\n{files_text}\n")


def display_diff(state: AgentState) -> None:
    diff_result = state.diff_result
    if not diff_result:
        return

    # Test result banner
    if diff_result.tests_passed:
        console.print("[bold green]✅ Sandbox tests PASSED[/]")
    else:
        console.print("[bold red]❌ Sandbox tests FAILED[/]")
        console.print(Panel(
            diff_result.test_output[:1000],
            title="Test Output",
            border_style="red",
        ))

    # Pretty diff
    syntax = Syntax(
        diff_result.diff_text,
        "diff",
        theme="monokai",
        line_numbers=True,
        word_wrap=True,
    )
    console.print(Panel(syntax, title="📝 Proposed Diff", border_style="yellow"))


def collect_human_decision(state: AgentState) -> HumanDecision:
    """
    Pause execution and ask the human to approve, reject, or give feedback.
    Returns a HumanDecision object.
    """
    console.rule("[bold magenta]🧑 Human Review Required[/]")
    console.print()
    display_issue_summary(state)
    display_diff(state)

    if state.iteration_count >= state.max_iterations:
        console.print(f"[bold red]⚠️  Max iterations ({state.max_iterations}) reached.[/]")

    timeout_sec = int(os.environ.get("AUTO_APPROVE_TIMEOUT_SEC", 120))
    console.print(f"\n[bold yellow]⏳ You have {timeout_sec} seconds to respond before AUTO-APPROVAL.[/]")
    console.print(
        "\n[bold]What would you like to do?[/]\n"
        "  [green]a[/] — Approve and submit PR\n"
        "  [red]r[/] — Reject and skip this issue\n"
        "  [yellow]f[/] — Give feedback and regenerate\n"
        "Your choice [a/r/f] (default: r): ", end=""
    )

    # Cross-platform timeout wait using select (or fallback to auto-approve if select fails on some Windows terms)
    # The safest cross-platform way in standard library is threading + daemon
    choice = None
    
    def get_input():
        nonlocal choice
        try:
            choice = input().strip().lower()
        except EOFError:
            pass
            
    input_thread = threading.Thread(target=get_input, daemon=True)
    input_thread.start()
    input_thread.join(timeout=timeout_sec)
    
    if input_thread.is_alive():
        console.print("\n\n[bold yellow]⏰ Timeout reached. Automatically approving PR...[/]")
        return HumanDecision(action="approve")

    if not choice:
        choice = "r"

    if choice == "a":
        console.print("[bold green]✅ Approved! Submitting PR...[/]")
        return HumanDecision(action="approve")
    elif choice == "f":
        feedback = Prompt.ask("Enter your feedback for the agent")
        if feedback.strip():
            console.print(f"[bold yellow]💬 Feedback noted. Regenerating...[/]")
            return HumanDecision(action="feedback", feedback_text=feedback)
        else:
            console.print("[red]Feedback cannot be empty.[/]")
            return HumanDecision(action="reject")
    else:
        console.print("[bold red]❌ Rejected. Moving on.[/]")
        return HumanDecision(action="reject")
