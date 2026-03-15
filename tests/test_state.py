"""
Basic unit tests for state and utility functions.
Run with: pytest tests/
"""

import pytest
from src.agent.state import AgentState, GithubIssue, ImplementationPlan, DiffResult, HumanDecision


def test_agent_state_defaults():
    state = AgentState()
    assert state.candidate_issues == []
    assert state.selected_issue is None
    assert state.iteration_count == 0
    assert state.max_iterations == 3


def test_github_issue_model():
    issue = GithubIssue(
        issue_number=42,
        title="Fix typo in README",
        body="There is a typo on line 3.",
        url="https://github.com/owner/repo/issues/42",
        repo_full_name="owner/repo",
        repo_url="https://github.com/owner/repo",
        labels=["good first issue"],
        language="python",
    )
    assert issue.issue_number == 42
    assert "good first issue" in issue.labels


def test_human_decision_approve():
    decision = HumanDecision(action="approve")
    assert decision.action == "approve"
    assert decision.feedback_text is None


def test_human_decision_feedback():
    decision = HumanDecision(action="feedback", feedback_text="Use snake_case for variable names")
    assert decision.action == "feedback"
    assert "snake_case" in decision.feedback_text


def test_implementation_plan():
    plan = ImplementationPlan(
        summary="Fix the off-by-one error in list indexing",
        files_to_modify=["src/utils.py"],
        steps=["Open src/utils.py", "Change index to i-1", "Run tests"],
        estimated_complexity="low",
    )
    assert plan.estimated_complexity == "low"
    assert len(plan.steps) == 3


def test_state_with_issue():
    issue = GithubIssue(
        issue_number=1,
        title="Test",
        body="body",
        url="https://github.com/a/b/issues/1",
        repo_full_name="a/b",
        repo_url="https://github.com/a/b",
    )
    state = AgentState(selected_issue=issue)
    assert state.selected_issue.repo_full_name == "a/b"
