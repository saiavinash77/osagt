"""
Scheduler
Runs the agent automatically on a configurable interval (default: every 6 hours).
Intended for 24/7 server deployments. The HITL step is handled via the Web UI.

Usage:
    python scheduler.py            # runs forever
    python scheduler.py --once     # single run then exit
"""

import argparse
import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from src.config.settings import settings
from src.utils.logging_setup import configure_logging
from src.utils.history import was_already_attempted, record_run
from src.agent.graph import build_graph
from src.agent.state import AgentState

configure_logging(settings.log_level, settings.log_file)
logger = logging.getLogger(__name__)


def run_once_headless() -> None:
    """
    Run scanner → architect → developer, then PAUSE.
    Since there's no terminal here, the human reviews via the Web UI.
    The Web UI (api.py) handles the HITL step separately.
    Use this scheduler together with the web server.
    """
    logger.info("⏰ Scheduler: starting agent run…")

    graph = build_graph()
    run_id = f"scheduled-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    config = {"configurable": {"thread_id": run_id}}

    initial = AgentState().model_dump()
    events = list(graph.stream(initial, config=config, stream_mode="values"))

    # Extract final state after breakpoint
    snapshot = graph.get_state(config=config)
    state = AgentState(**snapshot.values)

    if state.error_message:
        logger.error(f"Run failed: {state.error_message}")
        if state.selected_issue:
            record_run(
                repo_full_name=state.selected_issue.repo_full_name,
                issue_number=state.selected_issue.issue_number,
                issue_title=state.selected_issue.title,
                outcome="error",
                error=state.error_message,
            )
        return

    if state.diff_result and state.selected_issue:
        logger.info(
            f"✅ Diff ready for {state.selected_issue.repo_full_name}"
            f" #{state.selected_issue.issue_number}. "
            f"Open the Web UI to review and approve."
        )
    else:
        logger.warning("Scheduler run produced no diff.")


def main() -> None:
    parser = argparse.ArgumentParser(description="HITL Agent Scheduler")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    if not settings.auto_run and not args.once:
        logger.error(
            "AUTO_RUN is not enabled in .env. "
            "Set AUTO_RUN=true or pass --once to run manually."
        )
        return

    interval = settings.schedule_interval_hours * 3600

    if args.once:
        run_once_headless()
        return

    max_cycles = 6  # 6 cycles of 1hr work + 1hr sleep = 12 hours
    cycle = 0
    
    logger.info(f"Scheduler starting 12-hour session: {max_cycles} cycles of 1hr work + 1hr sleep.")
    
    while cycle < max_cycles:
        cycle += 1
        logger.info(f"--- Cycle {cycle}/{max_cycles} Started ---")
        try:
            run_once_headless()
        except Exception as e:
            logger.exception(f"Scheduler run crashed: {e}")

        if cycle < max_cycles:
            logger.info("Cycle complete. Sleeping for 1 hour before next run...")
            time.sleep(3600)  # Sleep exactly 1 hour
            
    logger.info("Scheduler completed all 12 hours.")


if __name__ == "__main__":
    main()
