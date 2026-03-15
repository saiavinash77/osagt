"""
Integration tests for the FastAPI web endpoints.
Uses TestClient — no actual agent runs fire (graph is mocked).
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from src.web.api import app, _runs
from src.agent.state import AgentState, GithubIssue, DiffResult, HumanDecision

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_runs():
    """Reset in-memory runs between tests."""
    _runs.clear()
    yield
    _runs.clear()


def _make_fake_run(status: str = "awaiting_review") -> str:
    """Inject a fake run into the store and return its ID."""
    issue = GithubIssue(
        issue_number=1, title="Test issue", body="body",
        url="https://github.com/a/b/issues/1",
        repo_full_name="a/b", repo_url="https://github.com/a/b",
    )
    diff = DiffResult(
        diff_text="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n",
        files_changed=["x.py"], tests_passed=True,
    )
    state = AgentState(selected_issue=issue, diff_result=diff)
    _runs["test01"] = {
        "graph": MagicMock(),
        "state": state,
        "status": status,
        "error": None,
    }
    return "test01"


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


# ── Start run ─────────────────────────────────────────────────────────────────

@patch("src.web.api._run_agent_to_breakpoint", new_callable=AsyncMock)
@patch("src.web.api.build_graph")
def test_start_run(mock_graph, mock_task):
    mock_graph.return_value = MagicMock()
    res = client.post("/api/run")
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data


# ── Get status ────────────────────────────────────────────────────────────────

def test_get_run_status_not_found():
    res = client.get("/api/run/nonexistent")
    assert res.status_code == 404


def test_get_run_status_awaiting():
    run_id = _make_fake_run("awaiting_review")
    res = client.get(f"/api/run/{run_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "awaiting_review"
    assert data["diff_text"] is not None
    assert data["repo"] == "a/b"


def test_get_run_status_completed():
    run_id = _make_fake_run("completed")
    res = client.get(f"/api/run/{run_id}")
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


# ── Submit decision ───────────────────────────────────────────────────────────

@patch("src.web.api._resume_after_decision", new_callable=AsyncMock)
def test_decision_approve(mock_resume):
    run_id = _make_fake_run("awaiting_review")
    res = client.post(f"/api/run/{run_id}/decision", json={"action": "approve"})
    assert res.status_code == 200

def test_decision_reject():
    run_id = _make_fake_run("awaiting_review")
    res = client.post(f"/api/run/{run_id}/decision", json={"action": "reject"})
    assert res.status_code == 200
    assert _runs[run_id]["status"] == "completed"


def test_decision_wrong_status():
    run_id = _make_fake_run("running")
    res = client.post(f"/api/run/{run_id}/decision", json={"action": "approve"})
    assert res.status_code == 400


def test_decision_not_found():
    res = client.post("/api/run/bad/decision", json={"action": "approve"})
    assert res.status_code == 404


# ── History ───────────────────────────────────────────────────────────────────

@patch("src.web.api.get_recent_prs", return_value=[])
def test_history_empty(mock_history):
    res = client.get("/api/history")
    assert res.status_code == 200
    assert res.json()["prs"] == []
