"""
Web UI Backend (FastAPI)
Exposes the agent as a REST API so you can review diffs in a browser
instead of the terminal. Useful when running the agent on a server.

Endpoints:
  POST /api/run           — start a new agent run
  GET  /api/run/{run_id}  — get run status & diff
  POST /api/run/{run_id}/decision — submit approve/reject/feedback
  GET  /api/history       — recent run history
  GET  /health            — health check
"""

import asyncio
import logging
import uuid
import os
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from src.agent.graph import build_graph
from src.agent.state import AgentState, HumanDecision
from src.utils.history import get_recent_prs, record_run

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HITL Contributor Agent",
    description="Human-in-the-Loop GitHub contribution agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory run store  {run_id: {"state": AgentState, "graph": ..., "status": str}}
_runs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class StartRunResponse(BaseModel):
    run_id: str
    message: str


class RunStatusResponse(BaseModel):
    run_id: str
    status: str       # "running" | "awaiting_review" | "completed" | "error"
    issue_title: Optional[str] = None
    issue_url: Optional[str] = None
    repo: Optional[str] = None
    plan_summary: Optional[str] = None
    diff_text: Optional[str] = None
    files_changed: Optional[list] = None
    tests_passed: Optional[bool] = None
    test_output: Optional[str] = None
    pr_url: Optional[str] = None
    error: Optional[str] = None
    iteration: Optional[int] = None


class DecisionRequest(BaseModel):
    action: Literal["approve", "reject", "feedback"]
    feedback_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Background task: run the graph up to the HITL breakpoint
# ---------------------------------------------------------------------------

async def _run_agent_to_breakpoint(run_id: str) -> None:
    """Runs scanner → architect → developer in the background thread pool."""
    run = _runs[run_id]
    graph = run["graph"]
    config = {"configurable": {"thread_id": run_id}}

    try:
        run["status"] = "running"
        initial = AgentState().model_dump()

        # Run synchronously in thread pool to not block the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: list(graph.stream(initial, config=config, stream_mode="values")),
        )

        snapshot = graph.get_state(config=config)
        state = AgentState(**snapshot.values)
        run["state"] = state

        if state.error_message:
            run["status"] = "error"
        elif state.diff_result:
            run["status"] = "awaiting_review"
            asyncio.create_task(_auto_approve_timeout(run_id))
        else:
            run["status"] = "error"

    except Exception as e:
        logger.exception(f"Agent run {run_id} crashed: {e}")
        run["status"] = "error"
        run["error"] = str(e)


async def _auto_approve_timeout(run_id: str) -> None:
    timeout_sec = int(os.environ.get("AUTO_APPROVE_TIMEOUT_SEC", 120))
    await asyncio.sleep(timeout_sec)
    
    run = _runs.get(run_id)
    if not run or run.get("status") != "awaiting_review":
        return
        
    logger.info(f"⏳ Timeout reached for run {run_id}. Auto-approving...")
    
    graph = run["graph"]
    config = {"configurable": {"thread_id": run_id}}
    decision = HumanDecision(action="approve")
    graph.update_state(config=config, values={"human_decision": decision})
    
    # Resume agent
    await _resume_after_decision(run_id)


async def _resume_after_decision(run_id: str) -> None:
    """Resumes the graph after the human injects a decision."""
    run = _runs[run_id]
    graph = run["graph"]
    config = {"configurable": {"thread_id": run_id}}

    try:
        run["status"] = "running"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: list(graph.stream(None, config=config, stream_mode="values")),
        )

        snapshot = graph.get_state(config=config)
        state = AgentState(**snapshot.values)
        run["state"] = state

        if state.pull_request:
            run["status"] = "completed"
            record_run(
                repo_full_name=state.selected_issue.repo_full_name,
                issue_number=state.selected_issue.issue_number,
                issue_title=state.selected_issue.title,
                outcome="approved",
                pr_url=state.pull_request.url,
            )
        elif state.human_decision and state.human_decision.action == "feedback":
            # Back at the breakpoint after feedback
            run["status"] = "awaiting_review"
        elif state.error_message:
            run["status"] = "error"
        else:
            run["status"] = "completed"

    except Exception as e:
        logger.exception(f"Resume {run_id} crashed: {e}")
        run["status"] = "error"
        run["error"] = str(e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/run", response_model=StartRunResponse)
async def start_run(background_tasks: BackgroundTasks):
    """Start a new agent run in the background."""
    run_id = str(uuid.uuid4())[:8]
    _runs[run_id] = {
        "graph": build_graph(),
        "state": None,
        "status": "pending",
        "error": None,
    }
    background_tasks.add_task(_run_agent_to_breakpoint, run_id)
    return StartRunResponse(run_id=run_id, message="Agent started. Poll /api/run/{run_id} for status.")


@app.get("/api/run/{run_id}", response_model=RunStatusResponse)
def get_run_status(run_id: str):
    """Get the current status and diff for a run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run = _runs[run_id]
    state: Optional[AgentState] = run.get("state")
    resp = RunStatusResponse(
        run_id=run_id,
        status=run["status"],
        error=run.get("error"),
    )

    if state:
        if state.selected_issue:
            resp.issue_title = state.selected_issue.title
            resp.issue_url = state.selected_issue.url
            resp.repo = state.selected_issue.repo_full_name
        if state.implementation_plan:
            resp.plan_summary = state.implementation_plan.summary
        if state.diff_result:
            resp.diff_text = state.diff_result.diff_text
            resp.files_changed = state.diff_result.files_changed
            resp.tests_passed = state.diff_result.tests_passed
            resp.test_output = state.diff_result.test_output
        if state.pull_request:
            resp.pr_url = state.pull_request.url
        resp.iteration = state.iteration_count
        resp.error = resp.error or state.error_message

    return resp


@app.post("/api/run/{run_id}/decision")
async def submit_decision(run_id: str, body: DecisionRequest, background_tasks: BackgroundTasks):
    """Submit a human decision (approve / reject / feedback) to a paused run."""
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run = _runs[run_id]
    if run["status"] != "awaiting_review":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting review (current status: {run['status']})"
        )

    graph = run["graph"]
    config = {"configurable": {"thread_id": run_id}}
    decision = HumanDecision(action=body.action, feedback_text=body.feedback_text)

    graph.update_state(config=config, values={"human_decision": decision})

    if body.action == "reject":
        run["status"] = "completed"
        state: AgentState = run.get("state")
        if state and state.selected_issue:
            record_run(
                repo_full_name=state.selected_issue.repo_full_name,
                issue_number=state.selected_issue.issue_number,
                issue_title=state.selected_issue.title,
                outcome="rejected",
            )
        return {"message": "Rejected. No PR submitted."}

    background_tasks.add_task(_resume_after_decision, run_id)
    return {"message": f"Decision '{body.action}' received. Resuming agent…"}


@app.get("/api/history")
def get_history():
    """Return recent successful PRs."""
    return {"prs": get_recent_prs(limit=20)}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Simple UI Dashboard showing agent status."""
    runs_html = ""
    for r_id, r_data in reversed(list(_runs.items())):
        status = r_data.get("status", "unknown")
        
        details = ""
        state: AgentState = r_data.get("state")
        if state and state.selected_issue:
            details = f" | Working on: <a href='{state.selected_issue.url}'>#{state.selected_issue.issue_number}</a>"
        
        color = "black"
        if status == "awaiting_review": color = "orange"
        elif status == "completed": color = "green"
        elif status == "error": color = "red"
        
        runs_html += f"<li style='margin-bottom: 10px;'><strong>Run {r_id}</strong>: <span style='color:{color}; font-weight:bold;'>{status.upper()}</span>{details}</li>"
    
    if not runs_html:
        runs_html = "<li>No runs yet.</li>"
        
    html = f"""
    <html>
        <head>
            <title>HITL Contributor Dashboard</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; background: #f4f4f9; padding: 40px; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; }}
                .btn {{ display: inline-block; padding: 12px 24px; background: #007bff; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; text-decoration: none; }}
                .btn:hover {{ background: #0056b3; }}
                ul {{ list-style-type: none; padding: 0; }}
                li {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 5px solid #007bff; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🤖 HITL Agent Dashboard</h1>
                <p>Monitor your agent's activity and start new runs.</p>
                <hr>
                <h2>Recent Activity</h2>
                <ul>{{runs_html}}</ul>
                <hr>
                <h2>Controls</h2>
                <form onsubmit="event.preventDefault(); fetch('/api/run', {{method: 'POST'}}).then(() => setTimeout(() => window.location.reload(), 1000));">
                    <button type="submit" class="btn">🚀 Start New Agent Run</button>
                    <p style="font-size: 12px; color: #666; margin-top: 10px;">To run continuously 1hr on/1hr off, run <code>python scheduler.py</code> in the terminal.</p>
                </form>
            </div>
        </body>
    </html>
    """
    return html
