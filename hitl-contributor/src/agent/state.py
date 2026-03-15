"""
State definitions for the HITL Contribution Agent graph.
All nodes read from and write to this shared state object.
"""

from __future__ import annotations
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class GithubIssue(BaseModel):
    """Represents a single GitHub issue found by the scanner."""
    issue_number: int
    title: str
    body: str
    url: str
    repo_full_name: str          # e.g. "owner/repo"
    repo_url: str
    labels: List[str] = Field(default_factory=list)
    language: Optional[str] = None


class ImplementationPlan(BaseModel):
    """Architect node output: a structured plan to fix the issue."""
    summary: str                 # 1-paragraph explanation
    files_to_modify: List[str]   # relative paths
    steps: List[str]             # ordered action steps
    estimated_complexity: Literal["low", "medium", "high"] = "low"


class DiffResult(BaseModel):
    """Developer node output: actual code changes produced."""
    diff_text: str               # unified diff format
    files_changed: List[str]
    tests_passed: bool
    test_output: str = ""
    error: Optional[str] = None


class HumanDecision(BaseModel):
    """What the human decided after reviewing the diff."""
    action: Literal["approve", "reject", "feedback"]
    feedback_text: Optional[str] = None  # filled when action == "feedback"


class PullRequest(BaseModel):
    """Created PR details."""
    url: str
    number: int
    title: str
    branch_name: str


# ---------------------------------------------------------------------------
# Main graph state
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """
    The single shared state object passed between all LangGraph nodes.
    Each node receives the full state and returns a partial update dict.
    """

    # -- Scanner output --
    candidate_issues: List[GithubIssue] = Field(default_factory=list)
    selected_issue: Optional[GithubIssue] = None

    # -- Architect output --
    implementation_plan: Optional[ImplementationPlan] = None

    # -- Developer output --
    diff_result: Optional[DiffResult] = None

    # -- HITL --
    human_decision: Optional[HumanDecision] = None

    # -- Submission output --
    pull_request: Optional[PullRequest] = None

    # -- Control flow --
    current_node: str = "scanner"
    error_message: Optional[str] = None
    iteration_count: int = 0          # guards against infinite feedback loops
    max_iterations: int = 3

    class Config:
        arbitrary_types_allowed = True
