"""
Unit tests for agent nodes.
All external calls (GitHub API, LLM) are mocked.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agent.state import AgentState, GithubIssue, ImplementationPlan, DiffResult, HumanDecision


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_issue():
    return GithubIssue(
        issue_number=99,
        title="Fix off-by-one error in pagination",
        body="The pagination returns N+1 items on the last page.",
        url="https://github.com/testorg/testrepo/issues/99",
        repo_full_name="testorg/testrepo",
        repo_url="https://github.com/testorg/testrepo",
        labels=["good first issue", "bug"],
        language="python",
    )


@pytest.fixture
def sample_plan():
    return ImplementationPlan(
        summary="Fix the off-by-one in the paginate() function in utils.py",
        files_to_modify=["src/utils.py"],
        steps=["Open src/utils.py", "Change `items[:n+1]` to `items[:n]`", "Run tests"],
        estimated_complexity="low",
    )


@pytest.fixture
def sample_diff():
    return DiffResult(
        diff_text="--- a/src/utils.py\n+++ b/src/utils.py\n@@ -10,7 +10,7 @@\n-    return items[:n+1]\n+    return items[:n]\n",
        files_changed=["src/utils.py"],
        tests_passed=True,
        test_output="1 passed in 0.1s",
    )


# ── Scanner node tests ────────────────────────────────────────────────────────

class TestScannerNode:
    @patch("src.agent.nodes.scanner.search_good_first_issues")
    @patch("src.agent.nodes.scanner.get_llm")
    def test_scanner_selects_issue(self, mock_llm, mock_search, sample_issue):
        mock_search.return_value = [sample_issue.model_dump()]
        mock_response = MagicMock()
        mock_response.content = "0"
        mock_llm.return_value.invoke.return_value = mock_response

        from src.agent.nodes.scanner import scanner_node
        state = AgentState()
        result = scanner_node(state)

        assert result["selected_issue"] is not None
        assert result["selected_issue"].issue_number == 99
        assert len(result["candidate_issues"]) == 1

    @patch("src.agent.nodes.scanner.search_good_first_issues")
    def test_scanner_returns_error_when_no_issues(self, mock_search):
        mock_search.return_value = []

        from src.agent.nodes.scanner import scanner_node
        state = AgentState()
        result = scanner_node(state)

        assert "error_message" in result
        assert result["error_message"] is not None

    @patch("src.agent.nodes.scanner.search_good_first_issues")
    @patch("src.agent.nodes.scanner.get_llm")
    def test_scanner_handles_bad_llm_index(self, mock_llm, mock_search, sample_issue):
        """If LLM returns garbage index, should default to first issue."""
        mock_search.return_value = [sample_issue.model_dump()]
        mock_response = MagicMock()
        mock_response.content = "not_a_number"
        mock_llm.return_value.invoke.return_value = mock_response

        from src.agent.nodes.scanner import scanner_node
        state = AgentState()
        result = scanner_node(state)

        assert result["selected_issue"].issue_number == 99


# ── Architect node tests ──────────────────────────────────────────────────────

class TestArchitectNode:
    @patch("src.agent.nodes.architect.get_repo_file_tree")
    @patch("src.agent.nodes.architect.get_file_content")
    @patch("src.agent.nodes.architect.get_llm")
    def test_architect_produces_plan(self, mock_llm, mock_content, mock_tree, sample_issue):
        mock_tree.return_value = ["src/utils.py", "tests/test_utils.py"]
        mock_content.return_value = None
        mock_response = MagicMock()
        mock_response.content = '''{
            "summary": "Fix the pagination bug",
            "files_to_modify": ["src/utils.py"],
            "steps": ["Step 1", "Step 2"],
            "estimated_complexity": "low"
        }'''
        mock_llm.return_value.invoke.return_value = mock_response

        from src.agent.nodes.architect import architect_node
        state = AgentState(selected_issue=sample_issue)
        result = architect_node(state)

        assert result["implementation_plan"] is not None
        assert result["implementation_plan"].estimated_complexity == "low"

    def test_architect_fails_without_issue(self):
        from src.agent.nodes.architect import architect_node
        state = AgentState()
        result = architect_node(state)
        assert "error_message" in result


# ── Graph routing tests ───────────────────────────────────────────────────────

class TestGraphRouting:
    def test_route_after_scanner_ok(self, sample_issue):
        from src.agent.graph import route_after_scanner
        state = AgentState(selected_issue=sample_issue)
        assert route_after_scanner(state) == "architect"

    def test_route_after_scanner_error(self):
        from src.agent.graph import route_after_scanner
        state = AgentState(error_message="No issues found")
        assert route_after_scanner(state) == "end"

    def test_route_after_hitl_approve(self, sample_issue, sample_plan, sample_diff):
        from src.agent.graph import route_after_hitl
        state = AgentState(
            selected_issue=sample_issue,
            implementation_plan=sample_plan,
            diff_result=sample_diff,
            human_decision=HumanDecision(action="approve"),
        )
        assert route_after_hitl(state) == "submitter"

    def test_route_after_hitl_reject(self, sample_issue):
        from src.agent.graph import route_after_hitl
        state = AgentState(
            selected_issue=sample_issue,
            human_decision=HumanDecision(action="reject"),
        )
        assert route_after_hitl(state) == "end"

    def test_route_after_hitl_feedback_within_limit(self, sample_issue):
        from src.agent.graph import route_after_hitl
        state = AgentState(
            selected_issue=sample_issue,
            human_decision=HumanDecision(action="feedback", feedback_text="Use snake_case"),
            iteration_count=1,
            max_iterations=3,
        )
        assert route_after_hitl(state) == "developer"

    def test_route_after_hitl_feedback_at_limit(self, sample_issue):
        from src.agent.graph import route_after_hitl
        state = AgentState(
            selected_issue=sample_issue,
            human_decision=HumanDecision(action="feedback", feedback_text="Try again"),
            iteration_count=3,
            max_iterations=3,
        )
        assert route_after_hitl(state) == "end"
